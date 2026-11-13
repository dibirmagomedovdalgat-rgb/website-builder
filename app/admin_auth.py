from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import select
import bcrypt
from app.database import AsyncSessionLocal
from app.users.models import User
from config import settings

 # Класс для защиты админки
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request):
        form = await request.form() # Данные из формы
        username = form.get("username") # Имя
        password = form.get("password") # Пароль

        if not username or not password: # Если поля пустые отклоняется вход
            return False
        # Отдельная сессия с бд для админа 
        async with AsyncSessionLocal() as session:
            query = select(User).where(User.name == username) 
            result = await session.execute(query) # Запрос 
            user = result.scalars().first() # Ответ

            if user: # Если юзер нашелся
                password_bytes = password.encode('utf-8') # Перевод сыргого пароля в байты
                hashed_password = user.hashed_password # Хеш из бд
                # Если хеш с бд пришел как обычная строка то переводится в байты 
                hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
                is_password_correct = bcrypt.checkpw(password_bytes, hashed_bytes) # Проверка введеного пароля с хешем из бд
                # Если пароль правильный и роль админ или стафф 
                if is_password_correct and user.role =="admin": 
                    # Открытие сессии админа в браузере и запись Id и роли 
                    request.session.update({ 
                        "user_id": str(user.id),
                        "user_role": user.role
                    })
                    return True  # Вход разрешен
                    
        return False  # Запрет входа 
    # Выход из админки
    async def logout(self, request: Request):
        request.session.clear() # Стирание данных админа из сессии браузера
        return True 
    # Проверка прав админа при каждом клике 
    async def authenticate(self, request: Request):
        user_id = request.session.get("user_id")  # Id из сессии

        if not user_id:
            return False

        async with AsyncSessionLocal() as session:
            query = select(User).where(User.id == int(user_id))
            result = await session.execute(query)
            user = result.scalar_one_or_none()

        if not user or not user.is_active or user.role not in ["admin"]:
            request.session.clear()  # Отчистка сессии 
            return False

        return True

authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY) # Секретный ключ для всех сессий(берется из .env)
