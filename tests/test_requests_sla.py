from datetime import datetime, timedelta, timezone


def _get_manager_headers(client) -> dict[str, str]:
    res = client.post(
        "/api/auth/login",
        json={"email": "manager@technoservice.ua", "password": "Manager2026!"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_guest_create_and_track_request(client):
    services = client.get("/api/services").json()
    assert len(services) > 0
    service_id = services[0]["id"]

    create_res = client.post(
        "/api/requests",
        json={
            "service_id": service_id,
            "contact_name": "Гість Сергій Петрович",
            "contact_phone": "+380631112233",
            "device_type": "Ноутбук",
            "device_model": "Acer Nitro 5",
            "problem_description": "Не заряджається акумулятор при підключенні блока живлення.",
            "priority": "normal",
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["tracking_code"].startswith("SC-")
    assert created["status"] == "new"
    assert created["sla_deadline"] is not None

    track_res = client.get(f"/api/requests/track/{created['tracking_code']}")
    assert track_res.status_code == 200
    assert track_res.json()["id"] == created["id"]


def test_sla_deadline_scales_with_priority(client):
    service_id = client.get("/api/services").json()[0]["id"]
    base_payload = {
        "service_id": service_id,
        "contact_name": "Тест SLA",
        "contact_phone": "+380670001122",
        "device_type": "ПК",
        "device_model": "Custom Build",
        "problem_description": "Перевірка автоматичного розрахунку регламентного часу SLA.",
    }

    urgent = client.post("/api/requests", json={**base_payload, "priority": "urgent"}).json()
    low = client.post("/api/requests", json={**base_payload, "priority": "low"}).json()

    urgent_dt = datetime.fromisoformat(urgent["sla_deadline"])
    low_dt = datetime.fromisoformat(low["sla_deadline"])
    assert urgent_dt < low_dt


def test_invalid_fsm_status_transition_rejected(client):
    service_id = client.get("/api/services").json()[0]["id"]
    created = client.post(
        "/api/requests",
        json={
            "service_id": service_id,
            "contact_name": "Клієнт Статус",
            "contact_phone": "+380670002233",
            "device_type": "Ноутбук",
            "device_model": "Dell Latitude",
            "problem_description": "Перевірка заборони некоректного переходу статусів.",
        },
    ).json()

    mgr_headers = _get_manager_headers(client)
    # Спроба перевести заявку напряму з 'new' у 'completed' має бути заблокована
    patch_res = client.patch(
        f"/api/requests/{created['id']}",
        headers=mgr_headers,
        json={"status": "completed"},
    )
    assert patch_res.status_code == 422
    assert patch_res.headers["content-type"].startswith("application/problem+json")


def test_overdue_sla_detection_and_internal_comments_privacy(client):
    # Реєструємо клієнта та створюємо заявку
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "privacy.client@example.ua",
            "password": "ClientPass2026!",
            "full_name": "Клієнт Приватність",
            "phone": "+380509998877",
        },
    ).json()
    client_headers = {"Authorization": f"Bearer {reg['access_token']}"}
    mgr_headers = _get_manager_headers(client)

    service_id = client.get("/api/services").json()[0]["id"]
    created = client.post(
        "/api/requests",
        headers=client_headers,
        json={
            "service_id": service_id,
            "contact_name": "Клієнт Приватність",
            "contact_phone": "+380509998877",
            "device_type": "Ноутбук",
            "device_model": "Lenovo Legion 5",
            "problem_description": "Перегрів відеочипа під навантаженням, потрібна діагностика.",
        },
    ).json()
    req_id = created["id"]

    # Менеджер переводить у діагностику і ставить прострочений дедлайн SLA (-3 години)
    past_deadline = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    updated = client.patch(
        f"/api/requests/{req_id}",
        headers=mgr_headers,
        json={"status": "diagnostics", "sla_deadline": past_deadline},
    ).json()
    assert updated["is_overdue"] is True
    assert updated["sla_state"] == "overdue"

    # Менеджер додає 1 публічний і 1 внутрішній коментар
    client.post(
        f"/api/requests/{req_id}/comments",
        headers=mgr_headers,
        json={"body": "Публічне повідомлення для клієнта.", "is_internal": False},
    )
    client.post(
        f"/api/requests/{req_id}/comments",
        headers=mgr_headers,
        json={"body": "Службова нотатка тільки для інженерів.", "is_internal": True},
    )

    # Менеджер бачить обидва коментарі (2), клієнт і гість — лише публічний (1)
    mgr_view = client.get(f"/api/requests/{req_id}", headers=mgr_headers).json()
    cli_view = client.get(f"/api/requests/{req_id}", headers=client_headers).json()
    guest_view = client.get(f"/api/requests/track/{created['tracking_code']}").json()

    assert len(mgr_view["comments"]) == 2
    assert len(cli_view["comments"]) == 1
    assert len(guest_view["comments"]) == 1
    assert cli_view["comments"][0]["body"] == "Публічне повідомлення для клієнта."