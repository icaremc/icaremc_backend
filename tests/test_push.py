from tests.conftest import auth_header


def test_push_notify_requires_admin(client, patient_auth, admin_auth):
    payload = {
        "user_id": patient_auth["user_id"],
        "title": "Hello",
        "body": "Test push",
        "type": "test",
        "data": {"a": "1"},
    }
    denied = client.post("/api/v1/push/notify", json=payload, headers=auth_header(patient_auth["token"]))
    assert denied.status_code == 403

    ok = client.post("/api/v1/push/notify", json=payload, headers=auth_header(admin_auth["token"]))
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    notes = client.get("/api/v1/notifications", headers=auth_header(patient_auth["token"]))
    assert any(n["title"] == "Hello" for n in notes.json())
