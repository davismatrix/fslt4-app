export async function apiRequest(base, token, path, options, onUnauthorized) {
  const response = await fetch(base + '/api' + path, {
    ...options,
    headers: {Authorization: `Bearer ${token}`, ...options.headers},
  });
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
