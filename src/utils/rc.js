// Exact pattern copied from backend/app/services/rc_service.py:
// _RC_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$", re.IGNORECASE)
export const RC_PATTERN = /^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$/i

export function validateRcFormat(rc) {
  if (!rc || typeof rc !== 'string') return false
  const stripped = rc.trim().replace(/\s+/g, '')
  return RC_PATTERN.test(stripped)
}

