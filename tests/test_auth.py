# tests/test_auth.py

def test_register_success(client):
    r = client.post("/auth/register", json={"username": "alice", "password": "password123"})
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "alice"
    assert "id" in data
    assert data["is_active"] is True


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "bob", "password": "password123"})
    r = client.post("/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 409


def test_login_success(client):
    client.post("/auth/register", json={"username": "charlie", "password": "password123"})
    r = client.post("/auth/login", data={"username": "charlie", "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "dana", "password": "password123"})
    r = client.post("/auth/login", data={"username": "dana", "password": "wrongpass"})
    assert r.status_code == 401

def test_login_with_non_existent_username(client):
    r = client.post("/auth/login", data={"username": "unkown", "password": "1111"})
    assert r.status_code == 401
