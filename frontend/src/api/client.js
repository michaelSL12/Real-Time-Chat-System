// Central base URL for all HTTP requests to the backend API.
// In a larger setup, this would usually come from an environment variable.
const API_BASE_URL = "http://127.0.0.1:8000";

// Read the current access token directly from localStorage so API calls
// always use the latest authenticated session state.
export function getAccessToken() {
  return localStorage.getItem("access_token") || "";
}

// Small shared fetch wrapper used by all API modules.
// It applies JSON headers by default and automatically adds the Bearer token
// when the user is authenticated.
export async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  return response;
}

export { API_BASE_URL };