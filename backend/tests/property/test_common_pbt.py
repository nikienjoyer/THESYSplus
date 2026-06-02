"""Property-based tests for the THESYS+ ``common/`` validators and token helpers.

Each test references the Property number from design §13 and the EARS
requirement clause it validates:

* Property 9 — institutional email matcher          → Requirement 1.2 / 1.4
* Password strength                                  → Requirement 5.5
* Property 4 — opaque token entropy                 → Requirement 2.8
* Property 6 — sha256 idempotence                   → Requirement 2.8
* Property 1 — JWT round-trip                       → Requirement 2.6
* Property 4 — refresh token round-trip             → Requirement 2.10
* Property 7 — password salt uniqueness             → Requirement 8.4
* Property 5 — refresh family invariant             → Requirements 2.4, 2.9

Marked ``property`` so they can be selected/skipped explicitly.
"""

from __future__ import annotations

import re
import string

import pytest
from django.core.exceptions import ValidationError
from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

from common.tokens.jwt import issue_access_token, verify_access_token
from common.tokens.opaque import generate_opaque_token, sha256
from common.validators import is_institutional_email, validate_password_strength


pytestmark = pytest.mark.property


# ---------------------------------------------------------------------------
# Property 9 — institutional email matcher
# ---------------------------------------------------------------------------
#
# Inputs that end with ``pampangastateu.edu.ph`` (apex or multi-level
# subdomain) MUST match. Lookalikes (``notpampangastateu.edu.ph``,
# ``pampangastateu.edu.ph.evil.tld``, etc.) MUST NOT match.

# Local-part character class kept conservative to avoid generating
# inputs that are syntactically invalid emails for unrelated reasons.
_LOCAL_CHARS = string.ascii_letters + string.digits + '._%+-'

local_part = st.text(alphabet=_LOCAL_CHARS, min_size=1, max_size=24).filter(
    # Ensure no leading/trailing dot — real-world acceptors reject those
    # and we don't want to test edge cases that are independently invalid.
    lambda s: not s.startswith('.') and not s.endswith('.'),
)

# Subdomain label: 1–24 alphanumeric/hyphen, no leading/trailing hyphen.
subdomain_label = st.text(
    alphabet=string.ascii_lowercase + string.digits + '-',
    min_size=1,
    max_size=24,
).filter(lambda s: not s.startswith('-') and not s.endswith('-'))

# 0–3 subdomain labels joined with dots.
subdomain = st.lists(subdomain_label, min_size=0, max_size=3).map(
    lambda labels: '.'.join(labels)
)


@hyp_settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(local=local_part, sub=subdomain)
def test_property9_institutional_email_apex_and_subdomain_accepted(local, sub):
    """Property 9 — every email under ``pampangastateu.edu.ph`` is accepted.

    Validates Requirement 1.2 and Requirement 1.4 (the client-side mirror
    in Wave A14 must agree on the same domain set).
    """
    domain = 'pampangastateu.edu.ph' if not sub else f'{sub}.pampangastateu.edu.ph'
    email = f'{local}@{domain}'
    assert is_institutional_email(email), email
    # And case-insensitive — matches the citext column on disk.
    assert is_institutional_email(email.upper()), email.upper()


# A handful of explicit lookalike fixtures the regex MUST reject.
LOOKALIKE_FIXTURES = [
    'user@notpampangastateu.edu.ph',
    'user@pampangastateu.edu.ph.evil.tld',
    'user@pampangastateu-edu.ph',
    'user@example.com',
    'user@pampangastateu.edu',
    'user@pampanga.state.edu.ph',
    'user@.pampangastateu.edu.ph',
    'user@pampangastateu.edu.ph.',
    '@pampangastateu.edu.ph',
    'user@pampangastateu .edu.ph',
]


@pytest.mark.parametrize('email', LOOKALIKE_FIXTURES)
def test_property9_lookalikes_rejected(email: str):
    """Property 9 — lookalike domains MUST NOT pass.

    These are static fixtures because the hypothesis generator can't
    produce them with high probability; the regex correctness against
    these is the security-critical case.
    """
    assert not is_institutional_email(email), email


# ---------------------------------------------------------------------------
# Password strength
# ---------------------------------------------------------------------------
#
# validate_password_strength raises iff:
#   len(s) < 12  OR  no letter [A-Za-z]  OR  no digit [0-9].
# Equivalently: passes iff length ≥ 12 AND has a letter AND has a digit.

password_chars = st.text(
    alphabet=string.printable.replace('\x0b', '').replace('\x0c', ''),
    min_size=0,
    max_size=40,
)


def _expected_strength_ok(s: str) -> bool:
    return len(s) >= 12 and bool(re.search(r'[A-Za-z]', s)) and bool(re.search(r'[0-9]', s))


@hyp_settings(max_examples=200, deadline=None)
@given(s=password_chars)
def test_password_strength_matches_spec(s: str):
    """Strength check exactly mirrors the spec: ≥12 chars, ≥1 letter, ≥1 digit.

    Validates Requirement 5.5.
    """
    expected = _expected_strength_ok(s)
    if expected:
        # Should NOT raise.
        validate_password_strength(s)
    else:
        with pytest.raises(ValidationError) as excinfo:
            validate_password_strength(s)
        # The error code must be the canonical WEAK_PASSWORD constant.
        assert excinfo.value.code == 'WEAK_PASSWORD'


# ---------------------------------------------------------------------------
# Property 4 — opaque token entropy
# ---------------------------------------------------------------------------
#
# Generate a large batch of tokens and assert pairwise uniqueness. With
# ≥256 bits of entropy the birthday-bound collision probability after
# 100k draws is < 1e-30 — running 100k examples in CI is plenty.
#
# We do this OUTSIDE hypothesis (it would just call generate_opaque_token
# repeatedly with no parameters) but mark it ``@pytest.mark.property``
# via the module-level pytestmark so it sits with the other PBT tests.

def test_property4_opaque_token_entropy_no_collisions():
    """Property 4 — 100k generated tokens are pairwise unique.

    Validates Requirement 2.8 (≥256 bits of entropy).
    """
    n = 100_000
    seen: set[str] = set()
    for _ in range(n):
        seen.add(generate_opaque_token())
    assert len(seen) == n


def test_property4_opaque_token_min_length_and_charset():
    """Tokens are URL-safe base64 ≥43 chars (matches secrets.token_urlsafe(32))."""
    allowed = set(string.ascii_letters + string.digits + '-_')
    sample = [generate_opaque_token() for _ in range(1000)]
    for t in sample:
        assert len(t) >= 43, f'token too short: {t!r}'
        assert set(t) <= allowed, f'unexpected chars in: {t!r}'


# ---------------------------------------------------------------------------
# Property 6 — sha256 idempotence and shape
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=200, deadline=None)
@given(s=st.text())
def test_property6_sha256_idempotent_and_64_lowercase_hex(s: str):
    """Property 6 — sha256 is deterministic with a fixed shape.

    Validates Requirement 2.8 (token_hash column is a 64-char hex).
    """
    h1 = sha256(s)
    h2 = sha256(s)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in '0123456789abcdef' for c in h1)


# ---------------------------------------------------------------------------
# Property 1 — JWT round-trip
# ---------------------------------------------------------------------------

ROLES = st.sampled_from(('student', 'faculty', 'administrator'))


@hyp_settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(role=ROLES)
def test_property1_jwt_round_trip(role: str, fake_user):
    """Property 1 — verify(issue(u)) returns a payload with matching sub/role.

    Also asserts ``exp - iat == JWT_ACCESS_TTL_SECONDS`` (15 min) per
    Requirement 2.1, and that ``jti`` is present and unique across two
    successive issuances. Validates Requirement 2.6.
    """
    user = fake_user(role=role)
    token = issue_access_token(user)
    payload = verify_access_token(token)

    assert payload['sub'] == str(user.id)
    assert payload['role'] == role
    assert int(payload['exp']) - int(payload['iat']) == 900  # 15 minutes
    assert isinstance(payload['jti'], str) and len(payload['jti']) > 0

    # Different jti per issuance.
    other = verify_access_token(issue_access_token(user))
    assert payload['jti'] != other['jti']


# ---------------------------------------------------------------------------
# Property 4 — Refresh token round-trip (32.1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@hyp_settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    remember_me=st.booleans(),
    user_agent=st.one_of(st.none(), st.text(max_size=255).filter(lambda s: '\x00' not in s)),
    ip_address=st.one_of(
        st.none(),
        st.ip_addresses(v=4).map(str),
        st.ip_addresses(v=6).map(str),
    ),
)
def test_property4_refresh_token_round_trip(
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
    django_user_model,
):
    """Property 4 (round-trip) — persisting then loading a RefreshToken returns equivalent fields.

    Hypothesis generates synthetic RefreshToken field tuples (user_id, family_id,
    remember_me, expires_at, etc.); persisting then loading the row returns
    equivalent fields.

    **Validates: Requirement 2.10.**

    Tag: Feature: thesys-authentication, Property 4 (round-trip)
    """
    from auth_service.models import RefreshToken
    from common.tokens.opaque import generate_opaque_token, sha256
    from django.utils import timezone
    import datetime as dt
    import uuid

    # Create a real user in the database with a unique email
    unique_email = f'test-{uuid.uuid4()}@pampangastateu.edu.ph'
    user = django_user_model.objects.create_user(
        email=unique_email,
        password='TestPassword123',
        first_name='Test',
        last_name='User',
        role='student',
    )

    # Generate synthetic fields
    plaintext = generate_opaque_token()
    token_hash = sha256(plaintext)
    family_id = uuid.uuid4()
    ttl_seconds = 2592000 if remember_me else 86400  # 30 days or 24 hours
    expires_at = timezone.now() + dt.timedelta(seconds=ttl_seconds)

    # Persist the token
    original = RefreshToken.objects.create(
        user=user,
        token_hash=token_hash,
        family_id=family_id,
        parent=None,
        remember_me=remember_me,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Load it back
    loaded = RefreshToken.objects.get(id=original.id)

    # Assert round-trip equivalence
    assert loaded.user_id == user.id
    assert loaded.token_hash == token_hash
    assert loaded.family_id == family_id
    assert loaded.parent_id is None
    assert loaded.remember_me == remember_me
    assert loaded.user_agent == user_agent
    # IP address may be normalized by Django (e.g., '::ffff:0:0' -> '::ffff:0.0.0.0')
    # so we compare the normalized forms
    if ip_address is not None:
        from ipaddress import ip_address as parse_ip
        assert parse_ip(loaded.ip_address) == parse_ip(ip_address)
    else:
        assert loaded.ip_address is None
    assert loaded.revoked_at is None
    assert loaded.revoked_reason is None
    # expires_at comparison with tolerance for microsecond precision
    assert abs((loaded.expires_at - expires_at).total_seconds()) < 1


# ---------------------------------------------------------------------------
# Property 7 — Password salt uniqueness (32.3)
# ---------------------------------------------------------------------------

# Generate passwords that meet strength rules: ≥12 chars, ≥1 letter, ≥1 digit
password_meeting_strength = st.text(
    alphabet=string.ascii_letters + string.digits + string.punctuation,
    min_size=12,
    max_size=40,
).filter(
    lambda s: bool(re.search(r'[A-Za-z]', s)) and bool(re.search(r'[0-9]', s))
)


@pytest.mark.django_db
@hyp_settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(plaintext=password_meeting_strength)
def test_property7_password_salt_uniqueness(plaintext: str, django_user_model):
    """Property 7 (password hashing) — hashing same plaintext twice yields distinct hashes.

    Hypothesis text strategy for plaintexts meeting strength rules; hashing same
    plaintext twice yields distinct hash strings; both hashes verify true.

    **Validates: Requirement 8.4.**

    Tag: Feature: thesys-authentication, Property 7 (password hashing)
    """
    from accounts.services import set_password, verify_password
    import uuid

    # Create two users with unique emails
    user1 = django_user_model.objects.create_user(
        email=f'user1-{uuid.uuid4()}@pampangastateu.edu.ph',
        password='TempPassword123',
        first_name='User',
        last_name='One',
        role='student',
    )
    user2 = django_user_model.objects.create_user(
        email=f'user2-{uuid.uuid4()}@pampangastateu.edu.ph',
        password='TempPassword123',
        first_name='User',
        last_name='Two',
        role='student',
    )

    # Hash the same plaintext for both users
    set_password(user1, plaintext)
    set_password(user2, plaintext)

    # Reload to get fresh password hashes
    user1.refresh_from_db()
    user2.refresh_from_db()

    # Assert distinct hash strings (salt uniqueness)
    assert user1.password != user2.password, 'Hashes must differ due to unique salts'

    # Assert both verify true
    ok1, _ = verify_password(user1, plaintext)
    ok2, _ = verify_password(user2, plaintext)
    assert ok1, 'First hash must verify'
    assert ok2, 'Second hash must verify'


# ---------------------------------------------------------------------------
# Property 5 — Refresh family invariant (32.6)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@hyp_settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(chain_length=st.integers(min_value=1, max_value=5))
def test_property5_refresh_family_invariant(chain_length: int, django_user_model, client):
    """Property 5 (reuse detection revokes the family) — rotation chains inherit family_id.

    Hypothesis generates rotation chains of length n ≥ 1; every rotated descendant
    inherits the original family_id; calling revoke_family(family_id, reason) marks
    every still-active row in the family revoked atomically; presenting any
    previously-rotated plaintext to /refresh returns 401 REFRESH_TOKEN_REUSE_DETECTED.

    **Validates: Requirements 2.4, 2.9.**

    Tag: Feature: thesys-authentication, Property 5 (reuse detection)
    """
    from auth_service.services import issue_token_pair, rotate_refresh, revoke_family
    from auth_service.models import RefreshToken
    from common.errors import RefreshReuseDetected
    from types import SimpleNamespace
    import uuid

    # Create a real user with unique email
    user = django_user_model.objects.create_user(
        email=f'testuser-{uuid.uuid4()}@pampangastateu.edu.ph',
        password='TestPassword123',
        first_name='Test',
        last_name='User',
        role='student',
    )

    # Mock request object
    mock_request = SimpleNamespace(META={'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'test'})

    # Issue initial token pair
    pair = issue_token_pair(user, mock_request, remember_me=False)
    original_family_id = pair.refresh_row.family_id
    tokens = [pair.refresh_plaintext]

    # Rotate chain_length times
    current_plaintext = pair.refresh_plaintext
    for _ in range(chain_length):
        rotated_pair = rotate_refresh(current_plaintext, mock_request)
        tokens.append(rotated_pair.refresh_plaintext)
        current_plaintext = rotated_pair.refresh_plaintext

        # Assert family_id is inherited
        assert rotated_pair.refresh_row.family_id == original_family_id

    # All tokens in the chain (except the last) should now be revoked with reason='rotated'
    # The last token should still be active
    all_tokens_in_family = RefreshToken.objects.filter(family_id=original_family_id).order_by('created_at')
    assert all_tokens_in_family.count() == chain_length + 1

    for i, token_row in enumerate(all_tokens_in_family):
        if i < chain_length:
            # All but the last should be revoked with reason='rotated'
            assert token_row.revoked_at is not None
            assert token_row.revoked_reason == 'rotated'
        else:
            # The last should still be active
            assert token_row.revoked_at is None

    # Now revoke the entire family
    revoked_count = revoke_family(original_family_id, reason='admin_revoke')
    assert revoked_count == 1  # Only the last active token should be revoked

    # Verify all tokens are now revoked
    all_tokens_in_family = RefreshToken.objects.filter(family_id=original_family_id)
    for token_row in all_tokens_in_family:
        assert token_row.revoked_at is not None

    # Presenting any previously-rotated plaintext should raise RefreshReuseDetected
    # Pick a token from the middle of the chain (already revoked with reason='rotated')
    if chain_length > 0:
        old_token = tokens[0]  # The original token, now revoked
        with pytest.raises(RefreshReuseDetected):
            rotate_refresh(old_token, mock_request)
