from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from vocablens.auth.jwt import decode_token
from vocablens.infrastructure.repositories_users import SQLiteUserRepository
from vocablens.domain.user import User
from pathlib import Path

security = HTTPBearer()
user_repo = SQLiteUserRepository(Path("vocablens.db"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:

    try:
        user_id = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication",
        )

    user = user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user