import { useEffect, useRef } from "react";

export default function useWebSocket(roomId, token, onMessage) {
  const wsRef = useRef(null);

  useEffect(() => {
    // Open a room-scoped WebSocket connection only when both the room id
    // and access token are available.
    if (!roomId || !token) return;

    const url = `ws://127.0.0.1:8000/ws/rooms/${roomId}?token=${token}`;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    // Forward parsed backend events to the page-level handler so the UI
    // can decide how to update chat state.
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };

    wsRef.current = ws;

    // Close the socket when leaving the room or when dependencies change.
    return () => {
      ws.close();
    };
  }, [roomId, token, onMessage]);

  // Send a JSON event through the active room socket.
  const send = (payload) => {
    if (!wsRef.current) return;
    wsRef.current.send(JSON.stringify(payload));
  };

  return { send };
}