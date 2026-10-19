from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.config import MySettings


def test_get_chapa_banks_missing_secret_key(client):
    with patch.object(MySettings, "CHAPA_SECRET_KEY", ""):
        res = client.get("/api/v1/payments/chapa/banks")
        assert res.status_code == 400
        assert "Chapa secret key is not configured" in res.json()["detail"]


def test_get_chapa_banks_live_mocked(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"status": "success", "message": "Banks retrieved", "data": [{"id": 1, "name": "Commercial Bank of Ethiopia", "swift": "CBETETAA", "acct_length": 13}]}'
    mock_resp.json.return_value = {
        "status": "success",
        "message": "Banks retrieved",
        "data": [
            {
                "id": 1,
                "name": "Commercial Bank of Ethiopia",
                "swift": "CBETETAA",
                "acct_length": 13,
            }
        ],
    }

    with patch.object(MySettings, "CHAPA_SECRET_KEY", "CHASECK_TEST-123456"):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            for path in ["/api/v1/payments/chapa/banks", "/api/v1/payments/banks"]:
                res = client.get(path)
                assert res.status_code == 200, res.text
                data = res.json()
                assert data["status"] == "success"
                bank = data["data"][0]
                assert bank["name"] == "Commercial Bank of Ethiopia"
                assert bank["id"] == 1
                # Normalization ensures code & bank_code are set
                assert bank["code"] == "1"
                assert bank["bank_code"] == "1"


def test_get_chapa_banks_error_handling(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.content = b'{"status": "failed", "message": "Invalid API Key"}'
    mock_resp.json.return_value = {
        "status": "failed",
        "message": "Invalid API Key",
    }

    with patch.object(MySettings, "CHAPA_SECRET_KEY", "CHASECK_INVALID"):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            res = client.get("/api/v1/payments/chapa/banks")
            assert res.status_code == 400
            assert "Chapa error" in res.json()["detail"]
