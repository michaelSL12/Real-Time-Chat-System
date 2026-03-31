# Real-Time Chat System

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-framework-green)
![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-orange)
![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-blue)
![WebSockets](https://img.shields.io/badge/realtime-WebSockets-purple)
![Tests](https://img.shields.io/badge/tests-pytest-success)

A fullstack real-time chat application built with FastAPI, PostgreSQL, WebSockets, and a frontend client.

## Features

- JWT authentication
- Refresh token rotation
- Public and private chat rooms
- Real-time messaging with WebSockets
- Read receipts and unread tracking
- Token-bucket rate limiting
- Cursor-based pagination
- Alembic database migrations
- Docker and Docker Compose support
- Automated tests

---

# Architecture Overview

```
Client (Web / Frontend)
│
▼
FastAPI API
│
├── Routers
│   ├── Auth
│   ├── Rooms
│   ├── Messages
│   └── WebSockets
│
├── Services
│   ├── Authorization
│   ├── Rate Limiting
│   └── Realtime Manager
│
└── Database
    └── PostgreSQL (SQLAlchemy ORM)
```

The system separates responsibilities into:

### Routers

* Handle HTTP and WebSocket endpoints.

### Services

Contain core business logic:

* authorization rules
* rate limiting
* realtime broadcasting

### Database

* SQLAlchemy ORM models
* Alembic migrations
* PostgreSQL storage

---

# Core Chat Logic

The chat system implements several rules to control room behavior and permissions.

## Room Creation

Any authenticated user can create rooms.

Rooms can be:

* Public rooms
* Private rooms

---

## Public Rooms

Public rooms are visible to all users.

Rules:

* Any user can see the room in the public room list.
* Any user can **join the room themselves**.
* After joining, users can send messages.

---

## Private Rooms

Private rooms are restricted.

Rules:

* Only **members of the room** can see it.
* Users **cannot join private rooms themselves**.
* Only the **room owner can invite users**.

---

## Room Permissions

| Action                         | Who can do it   |
| ------------------------------ | --------------- |
| Create room                    | Any user        |
| Join public room               | Any user        |
| View private room              | Members only    |
| Invite users to private room   | Owner only      |
| Remove users from private room | Owner only      |
| Change room name               | Any room member |
| Delete messages                | Room owner      |

---

## Message Read Tracking

Each user has a **read pointer per room**.

When a user reopens a room:

1. The chat automatically **scrolls to the last message the user has read**.
2. A **visual marker appears below that message**.
3. Messages below the marker represent **new unread messages**.

This allows users to easily continue reading where they left off.

---

# Features

## Authentication

* JWT access tokens
* refresh tokens stored in the database
* refresh token rotation
* refresh token revocation
* logout from all sessions

---

## Rooms

* public rooms
* private rooms
* room membership system
* invitation system
* member nicknames per room

---

## Messaging

* real-time WebSocket messaging
* ordered message history
* cursor-based pagination
* read receipts
* message deletion by room owner

---

## Real-Time Communication

* WebSocket broadcasting per room
* multi-client message distribution
* ping/pong keepalive support

---

## Security

* bcrypt password hashing
* refresh token hashing
* room authorization checks
* message rate limiting

---

## Testing

* pytest test suite
* API tests
* WebSocket tests
* database isolation for tests

---

# Technology Stack

| Component              | Technology              |
| ---------------------- | ----------------------- |
| API framework          | FastAPI                 |
| ORM                    | SQLAlchemy              |
| Database               | PostgreSQL              |
| Realtime communication | WebSockets              |
| Authentication         | JWT                     |
| Password hashing       | Passlib (bcrypt)        |
| Database migrations    | Alembic                 |
| Testing                | Pytest                  |
| Containerization       | Docker / Docker Compose |

---

# Project Structure

```
.
├── main.py
├── database.py
├── auth.py
├── schemas.py
├── settings.py

├── models/
│   ├── user.py
│   ├── room.py
│   ├── message.py
│   └── token.py

├── routers/
│   ├── auth_routes.py
│   ├── room_routes.py
│   ├── message_routes.py
│   └── ws_routes.py

├── services/
│   ├── authz.py
│   ├── rate_limit.py
│   └── realtime.py

├── alembic/
│   ├── env.py
│   └── versions/

├── tests/
│   ├── test_auth.py
│   ├── test_rooms.py
│   ├── test_rate_limit.py
│   ├── test_refresh_tokens.py
│   ├── test_logout_all.py
│   ├── test_read_receipts.py
│   └── test_ws.py

├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

# Real-Time Messaging

Messages are sent through WebSockets.

Endpoint:

```
/ws/rooms/{room_id}
```

Supported events:

### Message

```json
{
  "type": "message",
  "content": "Hello"
}
```

### Read receipt

```json
{
  "type": "read",
  "message_id": 42
}
```

### Ping

```json
{
  "type": "ping"
}
```

The server broadcasts events only to connected members of the room.

---

# Rate Limiting

Message sending is protected by a **Token Bucket rate limiter**.

Default configuration:

* 5 messages per 10 seconds

This prevents spam and protects the server.

Implemented in:

```
services/rate_limit.py
```

---

# Database Migrations

Schema changes are managed with **Alembic**.

Run migrations:

```
alembic upgrade head
```

Create migration:

```
alembic revision --autogenerate -m "description"
```

---

# Running the Project (Docker)

Start all services:

```
docker-compose up --build
```

Services:

| Service     | Port |
| ----------- | ---- |
| Backend API | 8000 |
| Frontend    | 5173 |
| PostgreSQL  | 5433 |

---

# Running Locally

Install dependencies:

```
pip install -r requirements.txt
```

Run migrations:

```
alembic upgrade head
```

Start server:

```
uvicorn main:app --reload
```

API docs:

```
http://127.0.0.1:8000/docs
```

---

# Environment Configuration

The backend loads sensitive configuration from **environment variables** rather than storing secrets directly in the source code.

This includes:

* JWT authentication secret
* database connection URLs
* token expiration settings

The project uses a `.env` file for local development.

## Setup

A template file `.env.example` is included in the repository.

Create your local environment file:

```
cp .env.example .env
```

Then edit `.env` and set your real values.

Example:

```
SECRET_KEY=your_long_random_secret_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=20
REFRESH_TOKEN_EXPIRE_DAYS=7

DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/chat
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/chat_test
```

The `.env` file is excluded from version control via `.gitignore` to prevent accidental exposure of secrets.

Only `.env.example` is committed to the repository to document the required configuration variables.

---

# Running Tests

Install development dependencies:

```
pip install -r requirements-dev.txt
```

Run tests:

```
pytest
```

Tests run against an isolated test database.

---

# Security Considerations

The system includes:

* password hashing (bcrypt)
* hashed refresh tokens
* refresh token rotation
* refresh token revocation
* room authorization checks
* message rate limiting

---

# Possible Future Improvements

* Redis-based rate limiter
* Redis Pub/Sub for distributed WebSocket broadcasting
* message editing
* typing indicators
* user presence tracking
* push notifications
* horizontal scaling support

---

# Frontend

The project also includes a lightweight frontend client (Vite-based) used to interact with the backend and demonstrate real-time chat functionality.

The frontend connects to the backend via:

* REST API endpoints
* WebSocket events for live chat updates

---

# License

Educational project demonstrating backend architecture and real-time systems.
