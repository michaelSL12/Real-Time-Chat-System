def register(client, username: str, password: str = "password123"):
    return client.post("/auth/register", json={"username": username, "password": password})

def login(client, username: str, password: str = "password123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()

def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def test_logout_all_revokes_all_refresh_tokens(client):
    register(client, "alice")

    t1 = login(client, "alice")
    t2 = login(client, "alice")  # second session/device
    access = t1["access_token"]

    # logout all sessions
    r = client.post("/auth/logout_all", headers=auth_headers(access))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "logged_out_all"
    assert body["revoked"] >= 2

    # both refresh tokens should now fail
    r1 = client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    r2 = client.post("/auth/refresh", json={"refresh_token": t2["refresh_token"]})
    assert r1.status_code == 401
    assert r2.status_code == 401