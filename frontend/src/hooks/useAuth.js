import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";

// Small convenience hook for accessing shared authentication state.
export function useAuth() {
  return useContext(AuthContext);
}