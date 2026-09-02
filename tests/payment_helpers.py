from tests.conftest import auth_header


def pay_appointment(client, patient_token: str, appointment_id: str, amount: str) -> str:
    init = client.post(
        "/api/v1/payments/chapa/initiate",
        headers=auth_header(patient_token),
        json={"kind": "appointment", "amount": amount, "appointment_id": appointment_id},
    )
    assert init.status_code == 200, init.text
    tx_ref = init.json()["tx_ref"]
    webhook = client.post(
        "/api/v1/payments/chapa/webhook",
        json={"tx_ref": tx_ref, "status": "success", "amount": amount},
    )
    assert webhook.status_code == 200, webhook.text
    return tx_ref
