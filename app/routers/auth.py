from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import ProblemException
from app.models import User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Автентифікація"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register_client(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise ProblemException(
            status_code=409,
            title="Обліковий запис уже існує",
            detail="Користувач із такою електронною поштою вже зареєстрований у системі.",
            error_type="https://technoservice.ua/problems/email-already-exists",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        role="client",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ProblemException(
            status_code=401,
            title="Невірні облікові дані",
            detail="Перевірте правильність електронної пошти та пароля.",
            error_type="https://technoservice.ua/problems/invalid-credentials",
        )

    token = create_access_token(user_id=user.id, role=user.role)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)