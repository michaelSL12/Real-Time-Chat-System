import { apiFetch } from "./client";

// Convert backend message-related errors into readable frontend messages.
function getErrorMessage(data, fallback) {
  if (!data) return fallback;

  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item?.msg) return item.msg;
        return JSON.stringify(item);
      })
      .join(" | ");
  }

  return fallback;
}

// Load message history for a room.
// The backend returns messages in descending order, so the frontend reverses
// them to render the chat from oldest to newest.
export async function getRoomMessages(roomId, limit = 100) {
  const res = await apiFetch(
    `/rooms/${roomId}/messages?limit=${limit}&order=desc`
  );

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(getErrorMessage(data, "Failed to load messages"));
  }

  if (Array.isArray(data?.items)) {
    return {
      ...data,
      items: [...data.items].reverse(),
    };
  }

  return data;
}

// Delete a message in a room.
// The backend applies the ownership/permission rules for this operation.
export async function deleteRoomMessage(roomId, messageId) {
  const res = await apiFetch(`/rooms/${roomId}/messages/${messageId}`, {
    method: "DELETE",
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to delete message");
  }

  return data;
}