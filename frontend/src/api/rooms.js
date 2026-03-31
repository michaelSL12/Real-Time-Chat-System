import { apiFetch } from "./client";

// Load all public rooms visible to authenticated users.
export async function getPublicRooms() {
  const res = await apiFetch("/rooms");
  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to load public rooms");
  }

  return data;
}

// Load the rooms the current user is allowed to access,
// including joined public rooms and private rooms they belong to.
export async function getMyRooms() {
  const res = await apiFetch("/me/accessible_rooms");
  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to load my rooms");
  }

  return data;
}

// Load full metadata for a single room.
export async function getRoom(roomId) {
  const res = await apiFetch(`/rooms/${roomId}`);
  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to load room");
  }

  return data;
}

// Create a new public or private room.
export async function createRoom(payload) {
  const res = await apiFetch("/rooms", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to create room");
  }

  return data;
}

// Join a public room as the current user.
export async function joinRoom(roomId) {
  const res = await apiFetch(`/rooms/${roomId}/join`, {
    method: "POST",
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to join room");
  }

  return data;
}

// Rename an existing room.
// The backend enforces whether the current user is allowed to do this action.
export async function renameRoom(roomId, payload) {
  const res = await apiFetch(`/rooms/${roomId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to rename room");
  }

  return data;
}

// Invite a user into a private room by username.
// In practice, this is only available to the room owner.
export async function inviteUserToRoom(roomId, payload) {
  const res = await apiFetch(`/rooms/${roomId}/invite`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to invite user");
  }

  return data;
}

// Delete a room.
// The backend decides whether the current user has permission to do so.
export async function deleteRoom(roomId) {
  const res = await apiFetch(`/rooms/${roomId}`, {
    method: "DELETE",
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to delete room");
  }

  return data;
}

// Update the current user's nickname for a specific room.
export async function updateMyRoomNickname(roomId, payload) {
  const res = await apiFetch(`/rooms/${roomId}/my-nickname`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Failed to update nickname");
  }

  return data;
}