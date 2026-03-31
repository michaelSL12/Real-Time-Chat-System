import { createContext, useEffect, useMemo, useState } from "react";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Initialize auth state from localStorage so refreshes do not log the user out.
  const [accessToken, setAccessToken] = useState(
    localStorage.getItem("access_token") || ""
  );
  const [refreshToken, setRefreshToken] = useState(
    localStorage.getItem("refresh_token") || ""
  );
  const [username, setUsername] = useState(
    localStorage.getItem("username") || ""
  );

  // Keep the stored access token synchronized with React state.
  useEffect(() => {
    if (accessToken) {
      localStorage.setItem("access_token", accessToken);
    } else {
      localStorage.removeItem("access_token");
    }
  }, [accessToken]);

  // Persist the refresh token so the session can survive page reloads.
  useEffect(() => {
    if (refreshToken) {
      localStorage.setItem("refresh_token", refreshToken);
    } else {
      localStorage.removeItem("refresh_token");
    }
  }, [refreshToken]);

  // Persist the username for lightweight session-aware UI display.
  useEffect(() => {
    if (username) {
      localStorage.setItem("username", username);
    } else {
      localStorage.removeItem("username");
    }
  }, [username]);

  // Save all auth values returned after a successful login or registration flow.
  const login = ({ access_token, refresh_token, username }) => {
    setAccessToken(access_token || "");
    setRefreshToken(refresh_token || "");
    setUsername(username || "");
  };

  // Clear both in-memory and persisted auth state.
  const logout = () => {
    setAccessToken("");
    setRefreshToken("");
    setUsername("");
  };

  // Memoize the context value so consumers do not re-render unless auth state changes.
  const value = useMemo(
    () => ({
      accessToken,
      refreshToken,
      username,
      isAuthenticated: Boolean(accessToken),
      login,
      logout,
    }),
    [accessToken, refreshToken, username]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}