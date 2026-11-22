from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
from config import settings
from app.users.models import User
from app.database import get_db 

# Создание токена
def create_access_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(days=30) # Сколько времени будет работать токен
    payload = {
        "sub": str(user_id), # Id пользователя под ключем "sub"
        "exp": expire  # Времия окончания действия токена "exp"
    }
    
    # Шифрование по алгоритму HS256 SECRET_KEY берется из .env
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt # Возвращает токена

# Проверка токена
def get_token_from_cookie(request: Request):
    token = request.cookies.get("users_access_token") # Поиск токена в куках
    if not token: # Если токена нет
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Вы не авторизованы"
        )
    return token # Возврат токена если он есть

 # Возвращает готовый объект пользователя User
async def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"]) # Проверка подлинности токена
        user_id_str: str = payload.get("sub") # Id пользователя
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
        user_id = int(user_id_str) # Превращение str Id в int
        
    except jwt.ExpiredSignatureError:
        # Если срок токена истек:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Срок действия токена истек")
    except (jwt.InvalidTokenError, ValueError):
         # Если с токеном что-то не так
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")

    # Поиск юзера в бд по его Id
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None: # Если юзер не найден
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован или не активен",
        )

    return user # Возврат объекта пользователя 

CSRF_COOKIE_NAME = "csrf_token"

def get_or_create_csrf_token(request: Request, response: Response) -> str:
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return token


async def verify_csrf(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Отсутствует CSRF cookie")
    submitted_token = request.headers.get("X-CSRF-Token")

    if not submitted_token:
        form_data = await request.form()
        submitted_token = form_data.get("csrf_token")

    if not submitted_token or not secrets.compare_digest(cookie_token, str(submitted_token)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный CSRF-токен")
