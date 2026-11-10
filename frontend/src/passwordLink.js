// Invite and reset links look like https://portal/password#invite=TOKEN or #reset=TOKEN.
// The token stays in the fragment so it never reaches a server log or Referer header.
export function parsePasswordLink(url) {
  let hash;
  try {
    hash = new URL(url, 'https://portal.invalid').hash;
  } catch {
    return null;
  }
  const params = new URLSearchParams(hash.slice(1));
  const invite = params.get('invite');
  const token = invite || params.get('reset');
  return token ? {token, invite: Boolean(invite)} : null;
}
