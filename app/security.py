from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.errors import ProblemException
from app.models import User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _decode_user(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload.get("sub", 0))
    except (jwt.PyJWTError, ValueError):
        raise ProblemException(
            status_code=401,
            title="Недійсний токен авторизації",
            detail="Сесія завершилася або токен пошкоджено. Виконайте вхід повторно.",
            error_type="https://technoservice.ua/problems/invalid-token",
        )

    user = db.get(User, user_id)
    if user is None:
        raise ProblemException(
            status_code=401,
            title="Користувача не знайдено",
            detail="Обліковий запис, пов’язаний із токеном, більше не існує.",
            error_type="https://technoservice.ua/problems/user-not-found",
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    return _decode_user(credentials.credentials, db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise ProblemException(
            status_code=401,
            title="Потрібна автентифікація",
            detail="Для виконання цієї дії необхідно увійти в систему.",
            error_type="https://technoservice.ua/problems/unauthorized",
        )
    return _decode_user(credentials.credentials, db)


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "manager":
        raise ProblemException(
            status_code=403,
            title="Доступ заборонено",
            detail="Ця операція доступна виключно менеджеру сервісного центру.",
            error_type="https://technoservice.ua/problems/forbidden",
        )
    return current_user