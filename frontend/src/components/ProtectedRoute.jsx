import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

// Prevent unauthenticated users from opening protected pages.
// Users without an access token are redirected to the auth screen.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }

  return children;
}