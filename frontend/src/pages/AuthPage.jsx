import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { loginUser, registerUser } from "../api/auth";
import { useAuth } from "../hooks/useAuth";

export default function AuthPage() {
  const navigate = useNavigate();
  const { isAuthenticated, login } = useAuth();

  const [mode, setMode] = useState("login");
  const [formData, setFormData] = useState({
    username: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Prevent authenticated users from returning to the auth page.
  if (isAuthenticated) {
    return <Navigate to="/rooms" replace />;
  }

  // Keep the auth form controlled so the same state object can be used
  // for both login and registration flows.
  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    setError("");
  };

  // In register mode, the page creates the account first and then performs
  // a normal login so the user enters the app immediately.
  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (mode === "register") {
        await registerUser(formData);
      }

      const tokenData = await loginUser(formData);
      login({
        ...tokenData,
        username: formData.username,
      });

      navigate("/rooms");
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="auth-wrapper">
      <div className="card auth-card">
        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => handleModeChange("login")}
          >
            Login
          </button>

          <button
            type="button"
            className={`auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => handleModeChange("register")}
          >
            Register
          </button>
        </div>

        <h1>{mode === "login" ? "Welcome back" : "Create account"}</h1>
        <p className="muted-text">
          {mode === "login"
            ? "Log in to access your rooms and chat in real time."
            : "Create a new account, then we will log you in automatically."}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="form-label">
            Username
            <input
              className="form-input"
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
            />
          </label>

          <label className="form-label">
            Password
            <input
              className="form-input"
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </label>

          {error ? <div className="form-error">{error}</div> : null}

          <button className="btn btn-primary form-submit" type="submit" disabled={loading}>
            {loading
              ? "Please wait..."
              : mode === "login"
              ? "Login"
              : "Register and login"}
          </button>
        </form>
      </div>
    </section>
  );
}