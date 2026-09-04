from tests.conftest import auth_header


def test_patient_signup_login_me(client, unique_phone):
    phone = unique_phone("93")
    otp = client.post("/api/v1/auth/patient/otp", json={"phone": phone})
    assert otp.status_code == 200
    code = otp.json()["dev_code"]

    signup = client.post(
        "/api/v1/auth/patient/signup",
        json={"phone": phone, "password": "secret12", "otp": code, "full_name": "Ada"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "patient"

    login = client.post("/api/v1/auth/patient/login", json={"phone": phone, "password": "secret12"})
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["refresh_token"]


def test_refresh_and_logout(client, unique_phone):
    phone = unique_phone("95")
    code = client.post("/api/v1/auth/patient/otp", json={"phone": phone}).json()["dev_code"]
    signup = client.post(
        "/api/v1/auth/patient/signup",
        json={"phone": phone, "password": "secret12", "otp": code, "full_name": "Refresh"},
    )
    assert signup.status_code == 200
    old_refresh = signup.json()["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["access_token"]
    assert body["refresh_token"] != old_refresh

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert logout.status_code == 200
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert after.status_code == 401


def test_patient_login_wrong_password(client, patient_auth):
    res = client.post(
        "/api/v1/auth/patient/login",
        json={"phone": patient_auth["phone"], "password": "wrong-pass"},
    )
    assert res.status_code == 401


def test_doctor_signup_and_reject_patient_login(client, doctor_auth):
    res = client.post(
        "/api/v1/auth/patient/login",
        json={"phone": doctor_auth["phone"], "password": "secret12"},
    )
    assert res.status_code == 401


def test_same_phone_patient_then_doctor(client, unique_phone):
    phone = unique_phone("94")
    password = "secret12"
    potp = client.post("/api/v1/auth/patient/otp", json={"phone": phone}).json()["dev_code"]
    patient = client.post(
        "/api/v1/auth/patient/signup",
        json={"phone": phone, "password": password, "otp": potp, "full_name": "Both"},
    )
    assert patient.status_code == 200, patient.text
    patient_id = patient.json()["user_id"]

    dotp = client.post("/api/v1/auth/doctor/otp", json={"phone": phone}).json()["dev_code"]
    doctor = client.post(
        "/api/v1/auth/doctor/signup",
        json={
            "phone": phone,
            "password": password,
            "otp": dotp,
            "first_name": "Both",
            "last_name": "Roles",
            "specialty": "OBGYN",
        },
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["user_id"] == patient_id
    assert set(doctor.json()["roles"]) == {"patient", "doctor"}

    plogin = client.post("/api/v1/auth/patient/login", json={"phone": phone, "password": password})
    dlogin = client.post("/api/v1/auth/doctor/login", json={"phone": phone, "password": password})
    assert plogin.status_code == 200
    assert dlogin.status_code == 200
    assert plogin.json()["role"] == "patient"
    assert dlogin.json()["role"] == "doctor"


def test_phone_taken(client, patient_auth):
    res = client.get("/api/v1/auth/phone-taken", params={"phone": patient_auth["phone"], "role": "patient"})
    assert res.status_code == 200
    assert res.json()["taken"] is True


def test_password_reset(client, patient_auth):
    otp = client.post("/api/v1/auth/password/otp", json={"phone": patient_auth["phone"]})
    assert otp.status_code == 200
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={
            "phone": patient_auth["phone"],
            "otp": otp.json()["dev_code"],
            "new_password": "newsecret",
        },
    )
    assert reset.status_code == 200
    login = client.post(
        "/api/v1/auth/patient/login",
        json={"phone": patient_auth["phone"], "password": "newsecret"},
    )
    assert login.status_code == 200


def test_admin_bootstrap_and_login(client):
    boot = client.post(
        "/api/v1/admin/bootstrap-super-admin",
        json={"email": "root@test.icaremc.app", "password": "adminpass123", "full_name": "Root"},
    )
    assert boot.status_code == 200
    again = client.post(
        "/api/v1/admin/bootstrap-super-admin",
        json={"email": "other@test.icaremc.app", "password": "adminpass123", "full_name": "Other"},
    )
    assert again.status_code == 403


def test_soft_delete(client, patient_auth):
    res = client.delete("/api/v1/auth/me", headers=auth_header(patient_auth["token"]))
    assert res.status_code == 200
    login = client.post(
        "/api/v1/auth/patient/login",
        json={"phone": patient_auth["phone"], "password": "secret12"},
    )
    assert login.status_code == 401


def test_me_unauthorized(client):
    assert client.get("/api/v1/auth/me").status_code == 401
