// Without a timeout, a stalled connection (e.g. a flaky tunnel or mobile network) leaves buttons disabled forever.
export const REQUEST_TIMEOUT = 30000;
export const UPLOAD_TIMEOUT = 5 * 60000;

export async function apiRequest(base, token, path, options, onUnauthorized) {
  const {timeout = REQUEST_TIMEOUT, signal, ...fetchOptions} = options;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {timedOut = true; controller.abort();}, timeout);
  // Still honour a caller's own cancellation (e.g. closing the PDF preview).
  const forwardAbort = () => controller.abort(signal.reason);
  if (signal) signal.aborted ? forwardAbort() : signal.addEventListener('abort', forwardAbort, {once: true});
  let response;
  try {
    response = await fetch(base + '/api' + path, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {Authorization: `Bearer ${token}`, ...fetchOptions.headers},
    });
  } catch (err) {
    if (timedOut) throw Error('The server did not respond in time. Check your connection, refresh the page to see whether the change was saved, and try again.');
    if (err.name === 'AbortError') throw err;
    throw Error('Could not reach the server. Check your connection and try again.');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', forwardAbort);
  }
  if (response.status === 401 && path !== '/login') onUnauthorized();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Error(typeof body.detail === 'string' ? body.detail : 'The request failed. Please try again.');
  }
  return response;
}

export async function logoutSession(request, clearSession) {
  try {
    await request('/logout', {method: 'POST'});
  } finally {
    clearSession();
  }
}
