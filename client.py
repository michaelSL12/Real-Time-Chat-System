import requests
from typing import Optional, Dict, Any, List

BASE_URL = "http://127.0.0.1:8000"


class ChatClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None

    # ---------- low-level helpers ----------
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _print_response(self, r: requests.Response):
        try:
            data = r.json()
        except Exception:
            data = r.text
        print(f"[{r.status_code}] {r.request.method} {r.url}")
        print(data)
        print("-" * 60)

    # ---------- auth ----------
    def register(self, username: str, password: str) -> bool:
        payload = {"username": username, "password": password}
        r = requests.post(self._url("/auth/register"), json=payload, headers=self._headers())
        if r.status_code in (200, 201):
            print(f"✅ Registered: {username}")
            return True

        # If user already exists, many APIs return 400; we’ll just continue.
        print(f"ℹ️ Register skipped (maybe already exists).")
        self._print_response(r)
        return False

    def login(self, username: str, password: str) -> bool:
        # Your API uses form-data for login (per your spec screenshot)
        data = {"username": username, "password": password}
        r = requests.post(self._url("/auth/login"), data=data)  # form-encoded
        if r.status_code != 200:
            print("❌ Login failed")
            self._print_response(r)
            return False

        token = r.json().get("access_token")
        if not token:
            print("❌ No access_token returned")
            self._print_response(r)
            return False

        self.token = token
        print(f"✅ Logged in as {username}")
        return True

    # ---------- rooms ----------
    def list_public_rooms(self) -> List[Dict[str, Any]]:
        r = requests.get(self._url("/rooms"))
        if r.status_code != 200:
            print("❌ Failed to list rooms")
            self._print_response(r)
            return []
        rooms = r.json()
        print(f"📋 Public rooms: {len(rooms)}")
        return rooms

    def my_rooms(self) -> List[Dict[str, Any]]:
        r = requests.get(self._url("/me/rooms"), headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to list my rooms")
            self._print_response(r)
            return []
        rooms = r.json()
        print(f"👤 My accessible rooms: {len(rooms)}")
        return rooms

    def create_room(self, name: str, is_private: bool = False) -> Optional[Dict[str, Any]]:
        payload = {"name": name, "is_private": is_private}
        r = requests.post(self._url("/rooms"), json=payload, headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to create room")
            self._print_response(r)
            return None
        room = r.json()
        print(f"✅ Room ready: {room['name']} (id={room['id']}, private={room['is_private']})")
        return room

    def join_room(self, room_id: int) -> bool:
        r = requests.post(self._url(f"/rooms/{room_id}/join"), headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to join room")
            self._print_response(r)
            return False
        print(f"✅ Joined room {room_id}")
        return True

    def invite_user(self, room_id: int, user_id: int) -> bool:
        r = requests.post(self._url(f"/rooms/{room_id}/invite/{user_id}"), headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to invite user")
            self._print_response(r)
            return False
        print(f"✅ Invited user {user_id} to room {room_id}")
        return True

    # ---------- messages ----------
    def post_message(self, room_id: int, content: str) -> Optional[Dict[str, Any]]:
        payload = {"content": content}
        r = requests.post(self._url(f"/rooms/{room_id}/messages"), json=payload, headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to post message (did you join first?)")
            self._print_response(r)
            return None
        msg = r.json()
        print(f"✅ Sent message id={msg['id']}")
        return msg

    def list_messages(
        self,
        room_id: int,
        limit: int = 20,
        order: str = "desc",
        before_id: Optional[int] = None,
        after_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        params = {"limit": limit, "order": order}
        if before_id is not None:
            params["before_id"] = before_id
        if after_id is not None:
            params["after_id"] = after_id

        r = requests.get(self._url(f"/rooms/{room_id}/messages"), params=params, headers=self._headers())
        if r.status_code != 200:
            print("❌ Failed to list messages")
            self._print_response(r)
            return None

        data = r.json()  # {"items": [...], "next_cursor": ...}
        return data


def demo():
    c = ChatClient()

    username = "alice"
    password = "password123"

    # 1) register (optional)
    c.register(username, password)

    # 2) login
    if not c.login(username, password):
        return

    # 3) list public rooms
    public_rooms = c.list_public_rooms()

    # 4) create a room (public)
    room = c.create_room("general", is_private=False)
    if not room:
        return
    room_id = room["id"]

    # 5) join room (must join first to post)
    c.join_room(room_id)

    # 6) post some messages
    c.post_message(room_id, "Hello from the new client 👋")
    c.post_message(room_id, "Now we support join-first + pagination!")

    # 7) read latest messages (desc)
    page1 = c.list_messages(room_id, limit=2, order="desc")
    if not page1:
        return

    print("\n--- Page 1 (latest, desc) ---")
    for m in page1["items"]:
        print(f"[{m['id']}] u{m['user_id']}: {m['content']}")

    next_cursor = page1.get("next_cursor")

    # 8) pagination: get older messages using before_id
    if next_cursor:
        page2 = c.list_messages(room_id, limit=2, order="desc", before_id=next_cursor)
        print("\n--- Page 2 (older, desc) ---")
        if page2:
            for m in page2["items"]:
                print(f"[{m['id']}] u{m['user_id']}: {m['content']}")
        else:
            print("(no more)")

    # 9) read messages oldest-first (asc)
    page_asc = c.list_messages(room_id, limit=5, order="asc")
    print("\n--- Oldest-first (asc) ---")
    if page_asc:
        for m in page_asc["items"]:
            print(f"[{m['id']}] u{m['user_id']}: {m['content']}")


if __name__ == "__main__":
    demo()