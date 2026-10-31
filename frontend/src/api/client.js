const rawApiUrl = (import.meta.env.VITE_API_URL !== undefined && import.meta.env.VITE_API_URL !== '')
  ? import.meta.env.VITE_API_URL
  : (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000');

// Ensure scheme is present if a bare host is supplied (e.g., from Render Blueprint property: host)
export const API_BASE_URL = (rawApiUrl && !rawApiUrl.startsWith('http://') && !rawApiUrl.startsWith('https://') && !rawApiUrl.startsWith('/'))
  ? `https://${rawApiUrl}`
  : rawApiUrl;

export class ApiError extends Error {
  constructor(message, status = 500, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Base fetch wrapper for making API requests with consistent error handling
 * and authorization headers.
 */
export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = {
    Accept: 'application/json',
    ...options.headers,
  };

  // Only set Content-Type to application/json if body is not FormData
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  // If a token exists in sessionStorage and Authorization isn't explicitly overridden, attach it
  const token = sessionStorage.getItem('invoiceiq_token');
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (networkError) {
    throw new ApiError(
      `Unable to connect to the InvoiceIQ backend server (${API_BASE_URL || 'current host'}). Please verify that the backend is running.`,
      0,
      networkError.message
    );
  }

  // Handle empty responses (like 204 No Content)
  if (response.status === 204) {
    return null;
  }

  let data = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    // Extract error detail from FastAPI response format ({"detail": "..."})
    let message = 'An unexpected error occurred.';
    if (data && data.detail) {
      if (typeof data.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        // Pydantic validation error array
        message = data.detail.map((err) => err.msg || `${err.loc?.join('.')} is invalid`).join(', ');
      }
    } else if (response.statusText) {
      message = response.statusText;
    }

    throw new ApiError(message, response.status, data);
  }

  return data;
}
