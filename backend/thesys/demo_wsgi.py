"""Normalize HTTPS forwarding from ngrok and Vercel for the loopback demo."""

from thesys.wsgi import application as django_application


def application(environ, start_response):
    # Vercel and ngrok both append their scheme, yielding "https, https".
    # Waitress rejects multiple X-Forwarded-Proto values. Accept only a chain
    # that consists entirely of HTTPS hops from the loopback tunnel agent.
    raw = environ.get('HTTP_X_FORWARDED_PROTO', '')
    schemes = [part.strip().lower() for part in raw.split(',')]
    if environ.get('REMOTE_ADDR') == '127.0.0.1' and schemes and all(
        scheme == 'https' for scheme in schemes
    ):
        environ['HTTP_X_FORWARDED_PROTO'] = 'https'
    else:
        environ.pop('HTTP_X_FORWARDED_PROTO', None)

    for name in ('HTTP_FORWARDED', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST',
                 'HTTP_X_FORWARDED_PORT', 'HTTP_X_FORWARDED_BY'):
        environ.pop(name, None)

    return django_application(environ, start_response)
