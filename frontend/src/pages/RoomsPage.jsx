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
  // The page uses both lists to decide which public rooms are still joinable.
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

  // Load the room data once when the page opens.
  useEffect(() => {
    loadRooms();
  }, []);

  // Build a quick lookup of the rooms the user already belongs to.
  // This makes it easy to filter those rooms out of the public list.
  const myRoomIds = useMemo(() => {
    return new Set(myRooms.map((room) => room.id));
  }, [myRooms]);

  // Public rooms that already exist in "My rooms" should not appear again
  // in the joinable public rooms section.
  const joinablePublicRooms = useMemo(() => {
    return publicRooms.filter((room) => !myRoomIds.has(room.id));
  }, [publicRooms, myRoomIds]);

  // Create a new room using the current form values, then refresh the lists.
  // After a successful creation, navigate directly into the new room.
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

      if (createdRoom?.id) {
        navigate(`/rooms/${createdRoom.id}`);
      }
    } catch (err) {
      setError(err.message || "Failed to create room");
    } finally {
      setLoading(false);
    }
  };

  // Join a public room, then refresh the page data so the room moves
  // from the public list into the user's own room list.
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
    <section className="card rooms-page">
      <h1 className="rooms-title">Rooms</h1>

      {error ? <div className="form-error">{error}</div> : null}

      <h2 className="subsection-title">Create room</h2>

      <div className="create-room-row">
        <input
          className="room-name-input"
          value={newRoomName}
          onChange={(e) => setNewRoomName(e.target.value)}
          placeholder="Room name"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !loading && newRoomName.trim()) {
              handleCreate();
            }
          }}
        />

        <label className="room-privacy-label">
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(e) => setIsPrivate(e.target.checked)}
          />
          Private room
        </label>

        <button
          className="create-room-btn"
          onClick={handleCreate}
          disabled={loading || !newRoomName.trim()}
        >
          {loading ? "Creating..." : "Create"}
        </button>
      </div>

      <h2 className="subsection-title">My rooms</h2>

      {myRooms.length === 0 ? (
        <p className="muted-text">No rooms yet.</p>
      ) : (
        <div className="rooms-list">
          {myRooms.map((room) => (
            <div key={room.id} className="room-item">
              <div>
                <div className="room-item-name">{room.name}</div>
                <div className="room-item-meta">
                  {room.is_private ? "Private" : "Public"}
                </div>
              </div>

              <button
                className="btn btn-light"
                onClick={() => openRoom(room)}
              >
                Open
              </button>
            </div>
          ))}
        </div>
      )}

      <h2 className="subsection-title">Public rooms</h2>

      {joinablePublicRooms.length === 0 ? (
        <p className="muted-text">No public rooms to join.</p>
      ) : (
        <div className="public-rooms-list">
          {joinablePublicRooms.map((room) => (
            <div key={room.id} className="room-item">
              <div>
                <div className="room-item-name">{room.name}</div>
                <div className="room-item-meta">Public</div>
              </div>

              <button
                className="btn btn-secondary"
                onClick={() => handleJoin(room.id)}
                disabled={loading}
              >
                {loading ? "Please wait..." : "Join"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}