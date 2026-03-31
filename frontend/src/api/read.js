import { apiFetch } from "./client";

// Convert backend read-tracking errors into readable frontend messages.
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

// Move the current user's read pointer forward to a specific message in the room.
// This is used to restore the user's place when they reopen the chat later.
export async function markMessageRead(roomId, messageId) {
  const res = await apiFetch(`/rooms/${roomId}/read/${messageId}`, {
    method: "POST",
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(getErrorMessage(data, "Failed to mark message as read"));
  }

  return data;
}

// Load the current user's saved read position for a room.
export async function getRoomReadStatus(roomId) {
  const res = await apiFetch(`/rooms/${roomId}/read`);
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(getErrorMessage(data, "Failed to load read status"));
  }

  return data;
}