/**
 * Sign-in helpers shared by the /sign-in page (SignInCard) and the landing
 * hero card (HeroSignInCard), so both validate and word errors the same way.
 */

/**
 * Validates institutional email (pampangastateu.edu.ph apex + subdomains)
 * Regex: ^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$
 */
export function isInstitutionalEmail(email) {
  const regex = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$/i;
  return regex.test(email);
}

export function mapSignInError(error) {
  const errorCode = error?.response?.data?.error?.code;
  const errorMessage = error?.response?.data?.error?.message;
  if (errorCode === 'INVALID_CREDENTIALS')  return 'Email or password is incorrect';
  if (errorCode === 'INVALID_EMAIL_DOMAIN') return 'Please use your institutional email address.';
  return errorMessage || 'An error occurred. Please try again.';
}
