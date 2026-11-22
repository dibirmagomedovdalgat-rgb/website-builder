import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Response 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.database import get_db
from app.users.models import User
from app.users.schemas import UserBase, UserCreate, UserResponse, UserLogin
from app.users.auth import create_access_token, get_current_user


router = APIRouter(prefix="/users", tags=["Пользователи"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Список условий проверок
    conditions = [
        User.name == user_data.name,
        User.email == user_data.email
    ]
    if user_data.phone: # Если юзер передал номер телефона он добавится в список проверок
        conditions.append(User.phone == user_data.phone)

    query = select(User).where(or_(*conditions)) # Запрос где передаются все условия
    result = await db.execute(query) # Запрос в бд
    existing_users = result.scalars().all() # Список всех совпадений

    # Проверка что именно совпало
    for existing_user in existing_users:
        # Если нашелся человек с таким же никнеймом 
        if existing_user.name == user_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким никнеймом уже зарегистрирован"
            )
        if existing_user.email == user_data.email:
            # Если есть пользователь с таким Email 
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован"
            )
        if user_data.phone and existing_user.phone == user_data.phone:
            # Если есть пользователь с таким номером телефона 
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким номером телефона уже зарегистрирован"
            )

    # Хеширование пароля
    password_bytes = user_data.password.encode('utf-8') # Перевод обычной строки в байты
    salt = bcrypt.gensalt() # Генерация шума(соли)
    hashed_password_str = bcrypt.hashpw(password_bytes, salt).decode('utf-8') # Хешироание пароля вместе с солью и превращение результата обратно в текст

    # Создание объекта
    new_user = User(
        name=user_data.name,  # Имя  
        email=user_data.email, # Email
        phone=user_data.phone, # Номер телефона
        bio=user_data.bio, # Биография(Описание)
        hashed_password=hashed_password_str # Хешированый пароль(str)
    )
    
    # Сохранение в бд
    db.add(new_user) # Добавление объекта в сессию бд
    await db.commit() # Запись
    await db.refresh(new_user) # Обновление инфы что б узнать Id
    
    return new_user # Возврат только что созданного юзера

@router.post("/login")
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    
    query = select(User).where(User.email == login_data.email) # Поиск юзера в бд по Email
    result = await db.execute(query) # Запрос 
    user = result.scalars().first() # Ответ

    if user: # Если юзер с таким Email нашелся
        password_bytes = login_data.password.encode('utf-8') # Перевод введеного пароля в байты
        hashed_bytes = user.hashed_password.encode('utf-8') # Перевод хеша пароля с бд в байты для проверки
        is_password_correct = bcrypt.checkpw(password_bytes, hashed_bytes) # bcrypt.checkpw Сравнивает присланый пароль с хешем
    # Если юзер с таким Email не нашелся 
    else:
        is_password_correct = False

    # Если юзера нет или пароль не соавпал
    if not user or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )
    
    # Генерация токене с помощью раннее созданной функции
    access_token = create_access_token(user_id=user.id)
    
    # Запись токена в куки браузера
    response.set_cookie(
        key="users_access_token",
        value=access_token, # Сам токен
        httponly=True, # Запрещает js читать куки
        max_age=30 * 24 * 3600, # Время жизни токена
        samesite="lax" # Защита от межсайтовых подделок
    )
    return {"message": "Вход успешно выполнен", "user_name": user.name} # Ответ если все прошло успешно

@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    profile_data: UserBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_name = profile_data.name.strip()
    new_email = profile_data.email.strip()
    new_phone = profile_data.phone.strip() if profile_data.phone and profile_data.phone.strip() else None
    new_bio = profile_data.bio.strip() if profile_data.bio and profile_data.bio.strip() else None

    if len(new_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Никнейм / Имя должно содержать минимум 2 символа",
        )

    conditions = [
        User.name == new_name,
        User.email == new_email,
    ]
    if new_phone:
        conditions.append(User.phone == new_phone)

    query = select(User).where(User.id != current_user.id, or_(*conditions))
    result = await db.execute(query)
    conflicts = result.scalars().all()

    for conflict in conflicts:
        if conflict.name == new_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот никнейм уже занят другим пользователем",
            )
        if conflict.email == new_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот email уже используется другим пользователем",
            )
        if new_phone and conflict.phone == new_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот номер телефона уже привязан к другому аккаунту",
            )

    current_user.name = new_name
    current_user.email = new_email
    current_user.phone = new_phone
    current_user.bio = new_bio

    await db.commit()
    await db.refresh(current_user)
    return current_user
