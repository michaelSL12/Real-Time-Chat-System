import { Link, useNavigate } from "react-router-dom";
import { logoutUser } from "../api/auth";
import { useAuth } from "../hooks/useAuth";

export default function Navbar() {
  const { isAuthenticated, refreshToken, logout, username } = useAuth();
  const navigate = useNavigate();

  // Try to revoke the current session on the backend first.
  // Even if that request fails, the frontend still clears local auth state
  // so the user is logged out from this client.
  const handleLogout = async () => {
    try {
      if (refreshToken) {
        await logoutUser(refreshToken);
      }
    } catch (error) {
      console.error("Logout request failed:", error);
    } finally {
      logout();
      navigate("/auth");
    }
  };

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">
          Chat App
        </Link>

        <nav className="nav-links">
          {isAuthenticated ? (
            <>
              <span className="user-badge">
                Signed in as <strong>{username || "User"}</strong>
              </span>
              <Link to="/rooms">Rooms</Link>
              <button className="btn btn-secondary" onClick={handleLogout}>
                Logout
              </button>
            </>
          ) : (
            <Link to="/auth">Login</Link>
          )}
        </nav>
      </div>
    </header>
  );
}