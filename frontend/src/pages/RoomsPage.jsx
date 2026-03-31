import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createRoom,
  getMyRooms,
  getPublicRooms,
  joinRoom,
} from "../api/rooms";

export default function RoomsPage() {
  const navigate = useNavigate();

  const [publicRooms, setPublicRooms] = useState([]);
  const [myRooms, setMyRooms] = useState([]);
  const [newRoomName, setNewRoomName] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load both the public room list and the current user's accessible rooms.
  // The page uses both lists to determine which public rooms are still joinable.
  const loadRooms = async () => {
    try {
      setError("");
      const [pub, mine] = await Promise.all([
        getPublicRooms(),
        getMyRooms(),
      ]);

      setPublicRooms(pub);
      setMyRooms(mine);
    } catch (err) {
      setError(err.message || "Failed to load rooms");
    }
  };

  useEffect(() => {
    loadRooms();
  }, []);

  // Build a fast lookup of rooms the user already has access to.
  const myRoomIds = useMemo(() => {
    return new Set(myRooms.map((room) => room.id));
  }, [myRooms]);

  // Public rooms that are already in "My rooms" should not appear
  // again in the joinable public rooms section.
  const joinablePublicRooms = useMemo(() => {
    return publicRooms.filter((room) => !myRoomIds.has(room.id));
  }, [publicRooms, myRoomIds]);

  const handleCreate = async () => {
    if (!newRoomName.trim()) return;

    try {
      setLoading(true);
      setError("");

      const createdRoom = await createRoom({
        name: newRoomName.trim(),
        is_private: isPrivate,
      });

      setNewRoomName("");
      setIsPrivate(false);

      await loadRooms();

      // Navigate directly into the room after successful creation
      // so the user can start chatting immediately.
      if (createdRoom?.id) {
        navigate(`/rooms/${createdRoom.id}`);
      }
    } catch (err) {
      setError(err.message || "Failed to create room");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async (roomId) => {
    try {
      setLoading(true);
      setError("");

      await joinRoom(roomId);
      await loadRooms();
    } catch (err) {
      setError(err.message || "Failed to join room");
    } finally {
      setLoading(false);
    }
  };

  // Pass the room name through navigation state so the chat page can show
  // a temporary title immediately before the full room request completes.
  const openRoom = (room) => {
    navigate(`/rooms/${room.id}`, {
      state: { roomName: room.name },
    });
  };

  return (
    <section className="card">
      <h1>Rooms</h1>

      {error ? <p style={{ color: "red" }}>{error}</p> : null}

      <h3>Create room</h3>

      <div style={{ display: "flex", gap: "10px", marginBottom: "12px", flexWrap: "wrap" }}>
        <input
          value={newRoomName}
          onChange={(e) => setNewRoomName(e.target.value)}
          placeholder="Room name"
        />

        <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(e) => setIsPrivate(e.target.checked)}
          />
          Private room
        </label>

        <button onClick={handleCreate} disabled={loading || !newRoomName.trim()}>
          Create
        </button>
      </div>

      <h3>My rooms</h3>

      {myRooms.length === 0 ? (
        <p>No rooms yet.</p>
      ) : (
        <ul>
          {myRooms.map((room) => (
            <li key={room.id} style={{ marginBottom: "10px" }}>
              <strong>{room.name}</strong>{" "}
              <span style={{ opacity: 0.7 }}>
                ({room.is_private ? "Private" : "Public"})
              </span>{" "}
              <button onClick={() => openRoom(room)}>
                Open
              </button>
            </li>
          ))}
        </ul>
      )}

      <h3>Public rooms</h3>

      {joinablePublicRooms.length === 0 ? (
        <p>No public rooms to join.</p>
      ) : (
        <ul>
          {joinablePublicRooms.map((room) => (
            <li key={room.id} style={{ marginBottom: "10px" }}>
              <strong>{room.name}</strong>{" "}
              <span style={{ opacity: 0.7 }}>(Public)</span>{" "}
              <button onClick={() => handleJoin(room.id)} disabled={loading}>
                Join
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}