import { apiFetch } from "./client";

// Convert backend error payloads into readable frontend error messages.
// Supports both simple string errors and FastAPI validation error arrays.
function getErrorMessage(data, fallback) {
  if (!data) return fallback;

  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item?.msg) {
          const field = Array.isArray(item.loc) ? item.loc.join(".") : "";
          return field ? `${field}: ${item.msg}` : item.msg;
        }
        return JSON.stringify(item);
      })
      .join(" | ");
  }

  return fallback;
}

// Register a new user through the backend auth API.
export async function registerUser(payload) {
  const response = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Registration failed"));
  }

  return data;
}

// Log in using the backend's expected form-encoded credentials format.
export async function loginUser(payload) {
  const formData = new URLSearchParams();
  formData.append("username", payload.username);
  formData.append("password", payload.password);

  const response = await apiFetch("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Login failed"));
  }

  return data;
}

// Log out the current session by sending the refresh token to the backend,
// which allows the server to revoke that session properly.
export async function logoutUser(refreshToken) {
  const response = await apiFetch("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Logout failed"));
  }

  return true;
}