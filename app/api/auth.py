from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import User, UserRole, get_session
from app.core.security import create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str


class ClientResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()

    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/register/ca", response_model=ClientResponse, status_code=status.HTTP_201_CREATED
)
async def register_ca_admin(
    payload: UserRegisterRequest, session: Session = Depends(get_session)
):
    """Public endpoint to register a new CA Admin account."""
    existing_user = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    ca_user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=UserRole.CA_ADMIN,
        hashed_password=User.hash_password(payload.password),
    )
    session.add(ca_user)
    session.commit()
    session.refresh(ca_user)

    return ClientResponse(
        id=ca_user.id,
        username=ca_user.username,
        full_name=ca_user.full_name,
        role=ca_user.role,
    )


@router.post(
    "/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED
)
async def onboard_client(
    payload: UserRegisterRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """CA Admin endpoint: Create and onboard a new Client under the active CA."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CA Admin access required to onboard clients",
        )

    existing_user = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )

    client_user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=UserRole.CLIENT,
        hashed_password=User.hash_password(payload.password),
    )
    session.add(client_user)
    session.commit()
    session.refresh(client_user)

    return ClientResponse(
        id=client_user.id,
        username=client_user.username,
        full_name=client_user.full_name,
        role=client_user.role,
    )


@router.get("/clients", response_model=list[ClientResponse])
async def list_clients(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """CA Admin endpoint: Retrieve a list of all registered client accounts."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CA Admin access required"
        )

    statement = select(User).where(User.role == UserRole.CLIENT)
    clients = session.exec(statement).all()

    return [
        ClientResponse(id=c.id, username=c.username, full_name=c.full_name, role=c.role)
        for c in clients
    ]
