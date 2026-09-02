from tests.conftest import auth_header


def _seed_week(client, admin_token: str, *, week_number: int = 8) -> str:
    h = auth_header(admin_token)
    week = client.post(
        "/api/v1/admin/pregnancy-weeks",
        headers=h,
        json={"week_number": week_number, "trimester": 1, "is_published": True},
    )
    assert week.status_code == 200, week.text
    week_id = week.json()["id"]
    en = client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "en", "title": "Week EN", "baby": "English baby"},
    )
    assert en.status_code == 200, en.text
    return week_id


def test_cms_falls_back_to_en(client, admin_auth):
    _seed_week(client, admin_auth["token"], week_number=8)
    resp = client.get("/api/v1/cms/pregnancy-weeks", params={"lang": "am"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["translation"]["title"] == "Week EN"
    assert rows[0]["lang_resolved"] == "en"


def test_cms_uses_requested_lang(client, admin_auth):
    week_id = _seed_week(client, admin_auth["token"], week_number=9)
    h = auth_header(admin_auth["token"])
    am = client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "am", "title": "ሳምንት", "baby": "አማርኛ"},
    )
    assert am.status_code == 200, am.text
    resp = client.get("/api/v1/cms/pregnancy-weeks", params={"lang": "am"})
    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["translation"]["title"] == "ሳምንት"
    assert row["lang_resolved"] == "am"


def test_cms_lang_from_profile_locale(client, admin_auth, patient_auth):
    week_id = _seed_week(client, admin_auth["token"], week_number=10)
    h_admin = auth_header(admin_auth["token"])
    client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h_admin,
        json={"language_code": "am", "title": "Profile AM", "baby": "x"},
    )
    h = auth_header(patient_auth["token"])
    patched = client.patch("/api/v1/me/profile", headers=h, json={"locale": "am"})
    assert patched.status_code == 200
    assert patched.json()["locale"] == "am"
    resp = client.get("/api/v1/cms/pregnancy-weeks", headers=h)
    assert resp.status_code == 200
    assert resp.json()[0]["lang_resolved"] == "am"
    assert resp.json()[0]["translation"]["title"] == "Profile AM"


def test_cms_lang_from_accept_language(client, admin_auth):
    week_id = _seed_week(client, admin_auth["token"], week_number=11)
    h = auth_header(admin_auth["token"])
    client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "om", "title": "OM week", "baby": "y"},
    )
    resp = client.get("/api/v1/cms/pregnancy-weeks", headers={"Accept-Language": "om-ET,om;q=0.9"})
    assert resp.status_code == 200
    assert resp.json()[0]["lang_resolved"] == "om"


def test_legal_falls_back_to_en(client, admin_auth):
    h = auth_header(admin_auth["token"])
    legal = client.put(
        "/api/v1/admin/legal-documents",
        headers=h,
        json={"slug": "terms", "locale": "en", "title": "Terms EN", "sections": [{"title": "A"}]},
    )
    assert legal.status_code == 200
    resp = client.get("/api/v1/cms/legal/terms", params={"lang": "am"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Terms EN"
    assert resp.json()["locale"] == "en"


def test_error_shape_is_detail(client):
    resp = client.get("/api/v1/cms/legal/missing-slug")
    assert resp.status_code == 404
    assert "detail" in resp.json()
