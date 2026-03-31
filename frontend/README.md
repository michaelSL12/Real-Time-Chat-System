# Real-Time Chat Frontend

![React](https://img.shields.io/badge/React-19-blue)
![Vite](https://img.shields.io/badge/Vite-frontend-purple)
![React Router](https://img.shields.io/badge/Routing-React_Router-red)
![WebSockets](https://img.shields.io/badge/realtime-WebSockets-green)

A lightweight frontend client for a real-time chat system built with React and Vite.

This application connects to the backend through:

* REST API requests
* WebSocket communication for live chat updates

It demonstrates a clean frontend structure for authentication, room management, and real-time messaging.

---

# Features

* user registration and login
* protected routes
* public and private rooms
* join public rooms from the UI
* invite users into private rooms
* rename rooms
* real-time messaging with WebSockets
* room owner message deletion
* automatic scroll to the user's last read message
* unread separator for continuing where the user stopped

---

# Core Chat Rules

The frontend follows the chat rules enforced by the backend.

## Room Creation

Any authenticated user can create rooms.

Rooms can be:

* Public
* Private

## Public Rooms

* Visible in the public rooms list
* Any user can join them by clicking **Join**
* Once joined, the room appears in the user's room list

## Private Rooms

* Visible only to room members
* Users cannot join them by themselves
* Only the room owner can invite other users by username

## Permissions

| Action                       | Who can do it          |
| ---------------------------- | ---------------------- |
| Create room                  | Any authenticated user |
| Join public room             | Any authenticated user |
| View private room            | Members only           |
| Invite users to private room | Owner only             |
| Rename room                  | Any room member        |
| Delete messages              | Room owner             |

---

# Read Tracking Behavior

Each room keeps track of the last message read by the current user.

When the user reopens a room:

1. The frontend fetches the room read status from the backend
2. The chat scrolls automatically to the last read message
3. A visual marker appears below that point
4. Messages below the marker are the unread messages

If live messages arrive while the user is not near the bottom, the UI shows a **new messages** banner with a button to jump to the latest messages.

---

# Tech Stack

| Component               | Technology   |
| ----------------------- | ------------ |
| UI library              | React        |
| Build tool              | Vite         |
| Routing                 | React Router |
| Styling                 | CSS          |
| HTTP communication      | Fetch API    |
| Real-time communication | WebSockets   |

---

# Project Structure

```id="fe8n4x"
src/
├── api/
│   ├── auth.js
│   ├── client.js
│   ├── messages.js
│   ├── read.js
│   └── rooms.js
├── components/
│   ├── Navbar.jsx
│   └── ProtectedRoute.jsx
├── context/
│   └── AuthContext.jsx
├── hooks/
├── pages/
│   ├── AuthPage.jsx
│   ├── ChatPage.jsx
│   └── RoomsPage.jsx
├── App.jsx
├── main.jsx
└── styles.css
```

---

# Running the Frontend

Install dependencies:

```id="ikf1q6"
npm install
```

Start development server:

```id="j0dr5r"
npm run dev
```

Default Vite development URL:

```id="xqyxq4"
http://127.0.0.1:5173
```

---

# Backend Dependency

This frontend is built to work with the matching FastAPI chat backend.

The backend provides:

* JWT authentication
* room and membership rules
* message APIs
* read tracking APIs
* WebSocket room communication

Make sure the backend server is running before starting the frontend.

---

# License

Educational project demonstrating frontend/backend integration in a real-time chat system.
