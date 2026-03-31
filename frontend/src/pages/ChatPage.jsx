import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import useWebSocket from "../hooks/useWebSocket";
import { getRoomMessages, deleteRoomMessage } from "../api/messages";
import { getRoomReadStatus, markMessageRead } from "../api/read";
import {
  getRoom,
  renameRoom,
  inviteUserToRoom,
  deleteRoom,
  updateMyRoomNickname,
} from "../api/rooms";

// Normalize backend datetime values so they can be parsed consistently
// even when the timezone suffix is missing.
function normalizeDateValue(value) {
  if (!value || typeof value !== "string") return value;
  const hasTimezone = /[zZ]$|[+\-]\d{2}:\d{2}$/.test(value);
  return hasTimezone ? value : `${value}Z`;
}

// Format message timestamps for compact chat display.
function formatTime(value) {
  if (!value) return "";
  const date = new Date(normalizeDateValue(value));
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ChatPage() {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { accessToken } = useAuth();

  const [room, setRoom] = useState(null);
  const [roomError, setRoomError] = useState("");
  const [roomNameInput, setRoomNameInput] = useState("");
  const [showRenameEditor, setShowRenameEditor] = useState(false);
  const [renaming, setRenaming] = useState(false);

  const [inviteUsername, setInviteUsername] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [inviting, setInviting] = useState(false);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [loadingMessages, setLoadingMessages] = useState(true);
  const [loadingRead, setLoadingRead] = useState(true);
  const [lastReadMessageId, setLastReadMessageId] = useState(null);
  const [currentUserId, setCurrentUserId] = useState(null);

  const [nickname, setNickname] = useState("");
  const [showNicknameEditor, setShowNicknameEditor] = useState(false);
  const [savingNickname, setSavingNickname] = useState(false);
  const [nicknameError, setNicknameError] = useState("");
  const [nicknameSuccess, setNicknameSuccess] = useState("");

  // Tracks whether live messages arrived while the user was away from the bottom
  // of the chat, so the UI can show a jump-to-latest banner.
  const [hasUnreadLiveMessages, setHasUnreadLiveMessages] = useState(false);

  const messagesContainerRef = useRef(null);

  // Refs are used here to coordinate one-time scroll behavior without forcing
  // extra renders. This keeps initial positioning and auto-scroll logic stable.
  const initialPositionDoneRef = useRef(false);
  const didInitialLoadRef = useRef(false);
  const shouldScrollToBottomRef = useRef(false);

  // Use the room name from navigation state as a temporary fallback until the
  // room details request finishes.
  const fallbackRoomName = location.state?.roomName || `Room ${roomId}`;
  const roomTitle = room?.name || fallbackRoomName;

  const isRoomOwner = room?.owner_id === currentUserId;

  // Only owners of private rooms can invite additional members.
  const canInviteMembers =
    room?.is_private && currentUserId && room?.owner_id === currentUserId;

  // Reset one-time scroll state whenever the user opens a different room.
  useEffect(() => {
    initialPositionDoneRef.current = false;
    didInitialLoadRef.current = false;
    setHasUnreadLiveMessages(false);
  }, [roomId]);

  // Load room metadata such as name, privacy, and ownership details.
  useEffect(() => {
    async function loadRoom() {
      try {
        setRoomError("");
        const data = await getRoom(roomId);
        setRoom(data);
        setRoomNameInput(data?.name || "");
      } catch (err) {
        console.error("loadRoom error:", err);
        setRoom(null);
        setRoomNameInput("");
        setRoomError(err.message || "Failed to load room");
      }
    }

    loadRoom();
  }, [roomId]);

  // Load the room message history when entering the room.
  useEffect(() => {
    async function loadMessages() {
      try {
        setLoadingMessages(true);
        setError("");
        const data = await getRoomMessages(roomId);
        setMessages(Array.isArray(data?.items) ? data.items : []);
      } catch (err) {
        console.error("loadMessages error:", err);
        setError(err.message || "Failed to load messages");
      } finally {
        setLoadingMessages(false);
      }
    }

    loadMessages();
  }, [roomId]);

  // Load the user's last read pointer so the chat can restore reading position.
  useEffect(() => {
    async function loadReadStatus() {
      try {
        setLoadingRead(true);
        const data = await getRoomReadStatus(roomId);
        setLastReadMessageId(data?.last_read_message_id ?? null);
      } catch (err) {
        console.error("loadReadStatus error:", err);
        setLastReadMessageId(null);
      } finally {
        setLoadingRead(false);
      }
    }

    loadReadStatus();
  }, [roomId]);

  // Infer the current user's nickname in this room from their existing messages.
  // This lets the nickname editor start with the value already visible in chat.
  useEffect(() => {
    if (!currentUserId) return;
    if (!messages.length) return;

    const myMessage = messages.find((msg) => msg.user_id === currentUserId);
    if (myMessage) {
      setNickname(myMessage.nickname || "");
    }
  }, [messages, currentUserId]);

  // Persist read progress only if the new message is ahead of the stored pointer.
  // This avoids unnecessary API calls and prevents moving the read marker backward.
  const saveReadIfNewer = useCallback(
    async (messageId) => {
      if (!messageId) return;
      if (lastReadMessageId && messageId <= lastReadMessageId) return;

      try {
        const result = await markMessageRead(roomId, messageId);
        setLastReadMessageId(result?.last_read_message_id ?? messageId);
      } catch (err) {
        console.error("saveReadIfNewer error:", err);
      }
    },
    [roomId, lastReadMessageId]
  );

  // Save the newest visible message as read, used when leaving the room manually.
  const saveLatestRoomMessageAsRead = useCallback(async () => {
    if (!messages.length) return;

    const latestMessage = messages[messages.length - 1];
    if (!latestMessage?.id) return;

    try {
      const result = await markMessageRead(roomId, latestMessage.id);
      setLastReadMessageId(result?.last_read_message_id ?? latestMessage.id);
    } catch (err) {
      console.error("saveLatestRoomMessageAsRead error:", err);
    }
  }, [messages, roomId]);

  // Treat the user as "near bottom" with a small threshold so the UI still feels
  // natural even if they are a few pixels above the exact bottom.
  const isNearBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return true;
    return container.scrollHeight - container.scrollTop - container.clientHeight < 60;
  }, []);

  const scrollToBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, []);

  // Handle WebSocket events for this room.
  // - "connected" gives the current authenticated user id
  // - "message" appends or updates live chat messages
  //
  // Auto-scroll behavior is intentionally conditional:
  // - always scroll for the current user's own message
  // - scroll for incoming messages only if the user is already near the bottom
  // - otherwise show a "new messages" banner instead of interrupting reading
  const handleIncoming = useCallback(
    (data) => {
      if (data.type === "connected") {
        setCurrentUserId(data.user_id ?? null);
        return;
      }

      if (data.type === "message") {
        const mine = currentUserId && data.user_id === currentUserId;
        const shouldStickToBottom = mine || isNearBottom();

        setMessages((prev) => {
          const exists = prev.some((msg) => msg.id === data.id);
          if (exists) {
            return prev.map((msg) => (msg.id === data.id ? { ...msg, ...data } : msg));
          }
          return [...prev, data];
        });

        if (mine) {
          saveReadIfNewer(data.id);
          shouldScrollToBottomRef.current = true;
        } else if (shouldStickToBottom) {
          shouldScrollToBottomRef.current = true;
        } else {
          setHasUnreadLiveMessages(true);
        }
      }
    },
    [currentUserId, isNearBottom, saveReadIfNewer]
  );

  const { send } = useWebSocket(roomId, accessToken, handleIncoming);

  // Restore the user's reading position once both messages and read status
  // are available. If no saved pointer exists, default to the latest messages.
  useEffect(() => {
    if (loadingMessages || loadingRead) return;
    if (initialPositionDoneRef.current) return;

    const container = messagesContainerRef.current;
    if (!container) return;

    if (lastReadMessageId) {
      const target = container.querySelector(
        `[data-message-id="${lastReadMessageId}"]`
      );

      if (target) {
        target.scrollIntoView({ block: "center", behavior: "auto" });
        initialPositionDoneRef.current = true;
        didInitialLoadRef.current = true;
        return;
      }
    }

    container.scrollTop = container.scrollHeight;
    initialPositionDoneRef.current = true;
    didInitialLoadRef.current = true;
  }, [loadingMessages, loadingRead, lastReadMessageId, messages]);

  // Perform deferred bottom scrolling after React has committed the new message list.
  useEffect(() => {
    if (!didInitialLoadRef.current) return;
    if (shouldScrollToBottomRef.current) {
      scrollToBottom();
      shouldScrollToBottomRef.current = false;
    }
  }, [messages, scrollToBottom]);

  // If the newest message belongs to the current user, mark it as read immediately.
  // This keeps the read pointer aligned with messages the user just sent themselves.
  useEffect(() => {
    if (!didInitialLoadRef.current) return;
    if (!currentUserId || messages.length === 0) return;

    const latestMessage = messages[messages.length - 1];
    if (latestMessage?.user_id === currentUserId) {
      saveReadIfNewer(latestMessage.id);
    }
  }, [messages, currentUserId, saveReadIfNewer]);

  // On room exit/unmount, persist the latest visible message as read so reopening
  // the room restores the correct continuation point.
  useEffect(() => {
    return () => {
      if (!messages.length) return;

      const latestMessage = messages[messages.length - 1];
      if (!latestMessage?.id) return;

      markMessageRead(roomId, latestMessage.id).catch((err) => {
        console.error("unmount mark read error:", err);
      });
    };
  }, [messages, roomId]);

  const sendMessage = () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    shouldScrollToBottomRef.current = true;

    send({
      type: "message",
      content: trimmed,
    });

    setInput("");
  };

  const handleRenameRoom = async () => {
    const trimmed = roomNameInput.trim();
    if (!trimmed) return;
    if (trimmed === room?.name) {
      setShowRenameEditor(false);
      return;
    }

    try {
      setRenaming(true);
      setRoomError("");

      const updatedRoom = await renameRoom(roomId, { name: trimmed });
      setRoom(updatedRoom);
      setRoomNameInput(updatedRoom?.name || trimmed);
      setShowRenameEditor(false);
    } catch (err) {
      console.error("handleRenameRoom error:", err);
      setRoomError(err.message || "Failed to rename room");
    } finally {
      setRenaming(false);
    }
  };

  const handleSaveNickname = async () => {
    try {
      setSavingNickname(true);
      setNicknameError("");
      setNicknameSuccess("");

      const result = await updateMyRoomNickname(roomId, {
        nickname: nickname.trim() || null,
      });

      const savedNickname = result?.nickname || "";

      setNickname(savedNickname);

      // Keep already-loaded chat messages visually in sync with the saved nickname
      // so the user sees the update immediately without refreshing the room.
      setMessages((prev) =>
        prev.map((msg) =>
          msg.user_id === currentUserId
            ? { ...msg, nickname: savedNickname || null }
            : msg
        )
      );

      setNicknameSuccess("Nickname updated.");
      setShowNicknameEditor(false);
    } catch (err) {
      console.error("handleSaveNickname error:", err);
      setNicknameError(err.message || "Failed to update nickname");
    } finally {
      setSavingNickname(false);
    }
  };

  const handleInviteUser = async () => {
    const trimmed = inviteUsername.trim();
    if (!trimmed) return;

    try {
      setInviting(true);
      setInviteError("");
      setInviteSuccess("");

      const result = await inviteUserToRoom(roomId, { username: trimmed });

      if (result?.status === "already_member") {
        setInviteSuccess(`"${trimmed}" is already in the room.`);
      } else {
        setInviteSuccess(`"${trimmed}" was invited successfully.`);
      }

      setInviteUsername("");
    } catch (err) {
      console.error("handleInviteUser error:", err);
      setInviteError(err.message || "Failed to invite user");
    } finally {
      setInviting(false);
    }
  };

  const handleDeleteRoom = async () => {
    const confirmed = window.confirm("Are you sure you want to delete this room?");
    if (!confirmed) return;

    try {
      setRoomError("");
      await deleteRoom(roomId);
      navigate("/rooms");
    } catch (err) {
      console.error("handleDeleteRoom error:", err);
      setRoomError(err.message || "Failed to delete room");
    }
  };

  const handleDeleteMessage = async (messageId) => {
    try {
      setError("");

      const updatedMessage = await deleteRoomMessage(roomId, messageId);

      // The backend returns an updated message object instead of removing it
      // completely, which allows the UI to display deleted-message state.
      setMessages((prev) =>
        prev.map((msg) => (msg.id === messageId ? updatedMessage : msg))
      );
    } catch (err) {
      console.error("handleDeleteMessage error:", err);
      setError(err.message || "Failed to delete message");
    }
  };

  const handleJumpToBottom = () => {
    scrollToBottom();
    setHasUnreadLiveMessages(false);

    const latestMessage = messages[messages.length - 1];
    if (latestMessage?.id) {
      saveReadIfNewer(latestMessage.id);
    }
  };

  const handleBackToRooms = async () => {
    await saveLatestRoomMessageAsRead();
    navigate("/rooms");
  };

  // Build UI-specific message data once so rendering stays simple and the JSX
  // does not need to repeat presentation logic on every field.
  const normalizedMessages = useMemo(() => {
    return messages.map((msg, index) => {
      const isMine = currentUserId ? msg.user_id === currentUserId : false;
      const senderLabel =
        msg.nickname ||
        msg.display_name ||
        msg.username ||
        `User ${msg.user_id ?? ""}`;

      const isLastMessage = index === messages.length - 1;

      // The read marker is rendered below the last message already read.
      // It is not shown after the final message because there would be no unread
      // content underneath it.
      const isReadMarker = msg.id === lastReadMessageId && !isLastMessage;

      return {
        ...msg,
        senderLabel,
        timeLabel: formatTime(msg.created_at),
        isMine,
        isReadMarker,
      };
    });
  }, [messages, lastReadMessageId, currentUserId]);

  const loading = loadingMessages || loadingRead;

  return (
    <section className="chat-page">
      <div className="chat-header-row">
        <button className="btn btn-light" onClick={handleBackToRooms}>
          Back to rooms
        </button>
        <h1 className="chat-title">{roomTitle}</h1>
      </div>

      <div className="chat-toolbar">
        <button
          className="btn btn-light"
          onClick={() => {
            setRoomNameInput(room?.name || "");
            setShowRenameEditor((prev) => !prev);
          }}
        >
          {showRenameEditor ? "Close rename" : "Rename room"}
        </button>

        <button
          className="btn btn-light"
          onClick={() => {
            setNicknameError("");
            setNicknameSuccess("");
            setShowNicknameEditor((prev) => !prev);
          }}
        >
          {showNicknameEditor ? "Close nickname" : "Change nickname"}
        </button>

        {isRoomOwner ? (
          <button className="btn btn-light" onClick={handleDeleteRoom}>
            Delete room
          </button>
        ) : null}
      </div>

      {showRenameEditor ? (
        <div className="nickname-card">
          <label className="form-label">
            New room name
            <input
              className="form-input"
              value={roomNameInput}
              onChange={(e) => setRoomNameInput(e.target.value)}
              placeholder="Enter new room name"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleRenameRoom();
                }
              }}
            />
          </label>

          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <button
              className="btn btn-primary"
              onClick={handleRenameRoom}
              disabled={renaming || !roomNameInput.trim()}
            >
              {renaming ? "Saving..." : "Save room name"}
            </button>

            <button
              className="btn btn-light"
              onClick={() => {
                setRoomNameInput(room?.name || "");
                setShowRenameEditor(false);
              }}
              disabled={renaming}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {showNicknameEditor ? (
        <div className="nickname-card">
          <label className="form-label">
            Nickname shown in this room
            <input
              className="form-input"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="Default: your username"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSaveNickname();
                }
              }}
            />
          </label>

          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <button
              className="btn btn-primary"
              onClick={handleSaveNickname}
              disabled={savingNickname}
            >
              {savingNickname ? "Saving..." : "Save nickname"}
            </button>

            <button
              className="btn btn-light"
              onClick={() => {
                setShowNicknameEditor(false);
                setNicknameError("");
                setNicknameSuccess("");
              }}
              disabled={savingNickname}
            >
              Cancel
            </button>
          </div>

          {nicknameError ? (
            <div className="form-error" style={{ marginTop: "10px" }}>
              {nicknameError}
            </div>
          ) : null}

          {nicknameSuccess ? (
            <div style={{ marginTop: "10px", color: "green" }}>
              {nicknameSuccess}
            </div>
          ) : null}
        </div>
      ) : null}

      {canInviteMembers ? (
        <div className="nickname-card">
          <label className="form-label">
            Invite user to this private room
            <input
              className="form-input"
              value={inviteUsername}
              onChange={(e) => setInviteUsername(e.target.value)}
              placeholder="Enter username"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleInviteUser();
                }
              }}
            />
          </label>

          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <button
              className="btn btn-primary"
              onClick={handleInviteUser}
              disabled={inviting || !inviteUsername.trim()}
            >
              {inviting ? "Inviting..." : "Invite"}
            </button>
          </div>

          {inviteError ? (
            <div className="form-error" style={{ marginTop: "10px" }}>
              {inviteError}
            </div>
          ) : null}

          {inviteSuccess ? (
            <div style={{ marginTop: "10px", color: "green" }}>
              {inviteSuccess}
            </div>
          ) : null}
        </div>
      ) : null}

      {roomError ? <div className="form-error">{roomError}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}

      <div className="chat-card">
        {hasUnreadLiveMessages ? (
          <div className="new-messages-banner">
            <span>You have new messages</span>
            <button className="btn btn-primary" onClick={handleJumpToBottom}>
              Jump to latest
            </button>
          </div>
        ) : null}

        <div
          className="chat-messages"
          ref={messagesContainerRef}
          onScroll={() => {
            if (isNearBottom()) {
              setHasUnreadLiveMessages(false);
            }
          }}
        >
          {loading ? (
            <p className="chat-empty">Loading messages...</p>
          ) : normalizedMessages.length === 0 ? (
            <p className="chat-empty">No messages yet.</p>
          ) : (
            normalizedMessages.map((msg, index) => (
              <div key={msg.id ?? index} data-message-id={msg.id}>
                <div className={`message-row ${msg.isMine ? "mine" : "other"}`}>
                  <div className={`message-bubble ${msg.isMine ? "mine" : "other"}`}>
                    <div className="message-sender">{msg.senderLabel}</div>

                    <div className={`message-content ${msg.is_deleted ? "deleted" : ""}`}>
                      {msg.content}
                    </div>

                    <div className="message-time">{msg.timeLabel}</div>

                    {isRoomOwner && !msg.is_deleted ? (
                      <button
                        className="btn btn-light"
                        onClick={() => handleDeleteMessage(msg.id)}
                        style={{ marginTop: "8px" }}
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </div>

                {msg.isReadMarker ? (
                  <div className="read-marker">Last read up to here</div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <div className="chat-input-row">
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type message..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                sendMessage();
              }
            }}
          />

          <button className="btn btn-primary chat-send-btn" onClick={sendMessage}>
            Send
          </button>
        </div>
      </div>
    </section>
  );
}