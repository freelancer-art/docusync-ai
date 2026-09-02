from typing import Callable, List
from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import User, UserRole, get_session
from app.core.security import get_current_user


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    """Dependency factory for enforcing Role-Based Access Control (RBAC)."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted: Insufficient privileges.",
            )
        return current_user

    return role_checker


# Quick alias dependencies for endpoint protection
require_admin = require_roles([UserRole.CA_ADMIN])
require_any_user = require_roles([UserRole.CA_ADMIN, UserRole.CLIENT])