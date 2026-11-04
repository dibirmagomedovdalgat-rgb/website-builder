import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.users.models import User
from app.users.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["Пользователи"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Проверки в одном запросе
    conditions = [
        User.name == user_data.name,
        User.email == user_data.email
    ]
    if user_data.phone:
        conditions.append(User.phone == user_data.phone)

    query = select(User).where(or_(*conditions))
    result = await db.execute(query)
    existing_users = result.scalars().all()

    # Проверка что именно совпало
    for existing_user in existing_users:
        if existing_user.name == user_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким никнеймом уже зарегистрирован"
            )
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован"
            )
        if user_data.phone and existing_user.phone == user_data.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким номером телефона уже зарегистрирован"
            )

    # Хеширование пароля
    password_bytes = user_data.password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password_str = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    # Создание объекта
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        phone=user_data.phone,
        bio=user_data.bio,
        hashed_password=hashed_password_str
    )
    
    # Сохранение в бд
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user
