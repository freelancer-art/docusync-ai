
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.api.deps import require_admin
from app.core.database import User, UserRole, get_session
from app.core.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["User Management"])


# --- Schemas ---
class UserCreateSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.CLIENT


class UserResponseSchema(BaseModel):
    id: int
    username: str
    full_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserUpdateSchema(BaseModel):
    full_name: str | None = None
    password: str | None = None
    role: UserRole | None = None


# --- Endpoints ---


@router.get("/me", response_model=UserResponseSchema)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Retrieve details for the currently authenticated user."""
    return current_user


@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreateSchema,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Allows CA Admins to provision new Client or CA Admin users."""
    existing_user = session.exec(
        select(User).where(User.username == user_in.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already registered.",
        )

    hashed_pw = User.hash_password(user_in.password)
    new_user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=hashed_pw,
        role=user_in.role,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


@router.get("/", response_model=list[UserResponseSchema])
def list_users(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Allows CA Admins to list all registered users in the system."""
    users = session.exec(select(User)).all()
    return users


@router.get("/{user_id}", response_model=UserResponseSchema)
def get_user_by_id(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Allows CA Admins to fetch a specific user profile by ID."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    return user


@router.patch("/{user_id}", response_model=UserResponseSchema)
def update_user(
    user_id: int,
    user_in: UserUpdateSchema,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Allows CA Admins to update user details, roles, or reset passwords."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.password is not None:
        user.hashed_password = User.hash_password(user_in.password)

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Allows CA Admins to delete a user account."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CA Admins cannot delete their own account.",
        )

    session.delete(user)
    session.commit()
