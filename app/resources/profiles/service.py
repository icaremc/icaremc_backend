from uuid import UUID

from app.api.v1.schemas import ProfileOut
from app.persistence.sqlalchemy.serialize import row_dict
from app.resources.errors import not_found
from app.resources.profiles.repository import ProfileRepository
from app.resources.profiles.schemas import ProfileUpdate


class ProfileService:
    def __init__(self, repo: ProfileRepository) -> None:
        self._repo = repo

    async def get_profile(self, user_id: UUID) -> ProfileOut:
        profile = await self._repo.get(user_id)
        if profile is None:
            raise not_found("Profile not found")
        return ProfileOut.model_validate(row_dict(profile))

    async def patch_profile(self, user_id: UUID, body: ProfileUpdate) -> ProfileOut:
        profile = await self._repo.get(user_id)
        if profile is None:
            raise not_found("Profile not found")
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(profile, key, value)
        await self._repo.flush()
        return ProfileOut.model_validate(row_dict(profile))
