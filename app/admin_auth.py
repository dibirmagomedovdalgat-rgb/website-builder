from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import select
import bcrypt

from app.database import AsyncSessionLocal
from app.users.models import User
from config import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form() 
        username = form.get("username")
        password = form.get("password")

        # Если поля пустые отклоняется вход
        if not username or not password:
            return False

        async with AsyncSessionLocal() as session:
            query = select(User).where(User.name == username) 
            result = await session.execute(query) 
            user = result.scalars().first()

            if user: 
                password_bytes = password.encode('utf-8')
                hashed_password = user.hashed_password
                hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
                
                # Проверка введеного пароля с хешем из бд
                is_password_correct = bcrypt.checkpw(password_bytes, hashed_bytes)
                
                if is_password_correct and user.role in ["admin", "staff"]: 
                    request.session.update({ 
                        "user_id": str(user.id),
                        "user_role": user.role
                    })
                    return True  # Вход разрешен
                    
        return False  # Запрет входа 
    
    async def logout(self, request: Request) -> bool:
        request.session.clear()  
        return True 

    async def authenticate(self, request: Request) -> RedirectResponse | bool:
        user_id = request.session.get("user_id") 
        user_role = request.session.get("user_role") 

        if user_id and user_role in ["admin", "staff"]: 
            return True 
            
        return False  


authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
