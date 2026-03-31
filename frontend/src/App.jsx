import { Navigate, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import AuthPage from "./pages/AuthPage";
import RoomsPage from "./pages/RoomsPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />

      <main className="page-container">
        {/* Route structure:
            - /auth stays public
            - /rooms and /rooms/:roomId require authentication
            - unknown routes fall back to the main app entry */}
        <Routes>
          <Route path="/" element={<Navigate to="/rooms" replace />} />
          <Route path="/auth" element={<AuthPage />} />

          <Route
            path="/rooms"
            element={
              <ProtectedRoute>
                <RoomsPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/rooms/:roomId"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}