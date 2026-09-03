from typing import Annotated

from fastapi import Depends

from app.persistence.sqlalchemy.deps import DbDep
from app.resources.auth.repository import SqlAlchemyAuthRepository
from app.resources.auth.service import AuthService


def get_auth_service(db: DbDep) -> AuthService:
    return AuthService(SqlAlchemyAuthRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
