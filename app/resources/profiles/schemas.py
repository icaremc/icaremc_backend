from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    account_type: str | None = None
    user_tracking_type: str | None = None
    locale: str | None = None
    dark_mode: bool | None = None
    notifications_enabled: bool | None = None
    fcm_token: str | None = None
    avatar_url: str | None = None
    location: str | None = None
    hospital: str | None = None
    onboarding_complete: bool | None = None
