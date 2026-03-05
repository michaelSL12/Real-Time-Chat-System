def register(client, username: str, password: str = "password123"):
    return client.post("/auth/register", json={"username": username, "password": password})

def login(client, username: str, password: str = "password123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()

def test_login_returns_refresh_token(client):
    register(client, "alice")
    data = login(client, "alice")
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_refresh_rotates_refresh_token(client):
    register(client, "bob")
    tokens1 = login(client, "bob")
    old_refresh = tokens1["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    tokens2 = r.json()

    assert tokens2["access_token"]
    assert tokens2["refresh_token"]
    assert tokens2["refresh_token"] != old_refresh  # rotation happened

    # old refresh should now be revoked
    r2 = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401

def test_logout_revokes_refresh_token(client):
    register(client, "carl")
    tokens = login(client, "carl")
    refresh = tokens["refresh_token"]

    out = client.post("/auth/logout", json={"refresh_token": refresh})
    assert out.status_code == 200

    # refresh after logout should fail
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401