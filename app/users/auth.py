from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    return user # Возврат объекта пользователя 