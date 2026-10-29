import { apiRequest } from './client';

export async function signupApi(name, email, password) {
  return apiRequest('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export async function loginApi(email, password) {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function getMeApi(token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  return apiRequest('/api/auth/me', {
    method: 'GET',
    headers,
  });
}
