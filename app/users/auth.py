# app/users/auth.py
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from app.users.models import User
from app.database import get_db 


# === 1. ЗДЕСЬ МЫ НАСТРАИВАЕМ СРОК НА 30 ДНЕЙ ===
def create_access_token(user_id: int) -> str:
    # Вычисляем время превращения токена в "тыкву" (текущее время + 30 дней)
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    
    payload = {
        "sub": str(user_id),
        "exp": expire  # Зашиваем это время внутрь токена под ключом "exp"
    }
    
    # Шифруем строку с помощью SECRET_KEY из вашего .env файла
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


# === 2. ЗДЕСЬ МЫ ПРОВЕРЯЕМ ЭТОТ СРОК ПРИ ЗАПРОСАХ ===
def get_token_from_cookie(request: Request) -> str:
    token = request.cookies.get("users_access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Вы не авторизованы"
        )
    return token

async def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: AsyncSession = Depends(get_db)
) -> User:
    try:
        # PyJWT автоматически прочитает поле "exp" и сравнит его с часами на сервере
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
        user_id = int(user_id_str)
        
    except jwt.ExpiredSignatureError:
        # Если дата exp осталась в прошлом — сработает этот блок:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Срок действия токена истек")
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")

    # Ищем пользователя в базе данных
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    return user
