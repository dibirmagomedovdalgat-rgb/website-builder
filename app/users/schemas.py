from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# Базовые поля пользователя, которые используются везде
class UserBase(BaseModel):
    name: str = Field(min_length=2, max_length=100) # Имя/Никнейм
    email: EmailStr # Email / Проверка, что строка является корректным email-адресом
    phone: str = Field(default=None, max_length=30) # Номер телефона
    bio: str | None = Field(default=None, max_length=1000) # Биография/О себе

# Регистрация. Добавляется пароль и все что в UserBase (включая телефон)
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=50) # Чистый пароль от 6 символов

# Данные, которые уходят наружу в Swagger и клиенту (сайт увидит и телефон)
class UserResponse(UserBase):
    id: int # Id
    image_path: str | None = None # Путь к аватарке
    is_active: bool # Проверка доступа к аккаунту true/false
    created_at: datetime # Дата создания аккаунта
    role: str # Роль (user, staff, admin)

    # Переводчик для Pydantic
    model_config = ConfigDict(from_attributes=True)

