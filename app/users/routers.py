import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Response 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.users.models import User
from app.users.schemas import UserCreate, UserResponse, UserLogin
from app.users.auth import create_access_token

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

@router.post("/login")
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    # 1. Ищем пользователя в базе данных по Email
    query = select(User).where(User.email == login_data.email)
    result = await db.execute(query)
    user = result.scalars().first()

    # ИСПРАВЛЕНО: Проверка пароля переписана под используемый вами bcrypt
    if user:
        password_bytes = login_data.password.encode('utf-8')
        hashed_bytes = user.hashed_password.encode('utf-8')
        is_password_correct = bcrypt.checkpw(password_bytes, hashed_bytes)
    else:
        is_password_correct = False

    # 2. Если пользователя нет или пароль не совпал
    if not user or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )
    
    # 3. Генерируем токен на 30 дней с помощью вашей функции из auth.py
    access_token = create_access_token(user_id=user.id)
    
    # 4. Записываем токен в куки ответа браузера
    response.set_cookie(
        key="users_access_token",  # Имя куки соответствует get_token_from_cookie
        value=access_token,
        httponly=True,             # Защита токена от XSS скриптов
        max_age=30 * 24 * 3600,    # Кука живет 30 дней в браузере
        samesite="lax"
    )
    
    return {"message": "Вход успешно выполнен", "user_name": user.name}
