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


def test_dispatch_notification_creates_db_record(patient_auth):
    import asyncio
    from uuid import UUID
    from app.persistence.sqlalchemy.connection import async_session_factory
    from app.resources.push.service import dispatch_notification

    uid = UUID(patient_auth["user_id"])

    async def _run():
        async with async_session_factory() as db:
            notif, fcm_res = await dispatch_notification(
                db=db,
                user_id=uid,
                title="Vaccine Due",
                body="Polio dose 1 is due",
                type="vaccine",
                data={"route": "/child/1/vaccines"},
                is_urgent=True,
            )
            assert notif.title == "Vaccine Due"
            assert notif.data["type"] == "vaccine"
            assert notif.data["click_action"] == "FLUTTER_NOTIFICATION_CLICK"
            assert notif.data["route"] == "/child/1/vaccines"
            assert fcm_res["ok"] is False
            assert fcm_res["skipped"] is True

    asyncio.run(_run())
