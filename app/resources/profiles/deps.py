from typing import Annotated

from fastapi import Depends

from app.persistence.sqlalchemy.deps import DbDep
from app.resources.profiles.repository import SqlAlchemyProfileRepository
from app.resources.profiles.service import ProfileService


def get_profile_service(db: DbDep) -> ProfileService:
    return ProfileService(SqlAlchemyProfileRepository(db))


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
