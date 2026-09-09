import httpx
import logging
from abc import ABC, abstractmethod


class SMSService(ABC):
    @abstractmethod
    async def send_sms(self, to: str, message: str) -> None:
        """Send an SMS message to a phone number."""
        pass


class AfroMessageService(SMSService):
    def __init__(self, api_key: str, sender_name: str = "", identifier_id: str = ""):
        self.api_key = api_key
        self.sender_name = sender_name
        self.identifier_id = identifier_id

    async def send_sms(self, to: str, message: str) -> None:
        if not self.api_key:
            print("WARNING: AfroMessage API key is not set. SMS not sent.")
            return

        params = {"to": to, "message": message}
        if self.sender_name:
            params["sender"] = self.sender_name
        if self.identifier_id:
            params["from"] = self.identifier_id

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.afromessage.com/api/send",
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            print(f"AfroMessage API response status: {response.status_code}")
            print(f"AfroMessage API response body: {response.text}")
            response.raise_for_status()
