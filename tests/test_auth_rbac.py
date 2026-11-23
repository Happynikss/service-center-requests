def test_healthcheck(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "technoservice-api"}


def test_register_and_login_client(client):
    reg_payload = {
        "email": "test.student@example.ua",
        "password": "StrongPass2026!",
        "full_name": "Тестовий Користувач Іванович",
        "phone": "+380679998877",
    }
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 201
    data = res_reg.json()
    assert data["user"]["role"] == "client"
    assert "access_token" in data

    res_login = client.post(
        "/api/auth/login",
        json={"email": "test.student@example.ua", "password": "StrongPass2026!"},
    )
    assert res_login.status_code == 200
    assert res_login.json()["user"]["email"] == "test.student@example.ua"


def test_duplicate_email_returns_rfc9457_problem(client):
    payload = {
        "email": "duplicate@example.ua",
        "password": "StrongPass2026!",
        "full_name": "Користувач Один",
        "phone": "+380671110000",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201

    res_dup = client.post("/api/auth/register", json=payload)
    assert res_dup.status_code == 409
    assert res_dup.headers["content-type"].startswith("application/problem+json")
    body = res_dup.json()
    assert body["status"] == 409
    assert "title" in body and "detail" in body and "instance" in body


def test_rbac_client_forbidden_on_manager_routes(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "client.rbac@example.ua",
            "password": "StrongPass2026!",
            "full_name": "Клієнт Перевірка Прав",
            "phone": "+380501234567",
        },
    ).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    assert client.get("/api/requests", headers=headers).status_code == 403
    assert client.get("/api/requests/stats", headers=headers).status_code == 403


def test_manager_login_and_dashboard_stats(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "manager@technoservice.ua", "password": "Manager2026!"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["role"] == "manager"
    assert body["user"]["full_name"] == "Демешко Микита Ігорович"

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    stats = client.get("/api/requests/stats", headers=headers)
    assert stats.status_code == 200
    assert "overdue" in stats.json()