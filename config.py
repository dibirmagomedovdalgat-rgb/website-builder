from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings): # Загрузка всех секретных ключей
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False  # Можно задать значение по умолчанию
    PORT: int = 8000

    # Откуда читать данные
    model_config = SettingsConfigDict(
        env_file=".env",            # Имя файла
        env_file_encoding="utf-8",  # Кодировка
        extra="ignore"              # Игнорировать лишние переменные в .env, если они есть
    )

# lru_cache Делает так что б .env читался один раз при старте сервера
@lru_cache
def get_settings():
    return Settings() # Объект настроек

# Для импорта
settings = get_settings()

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DOMAIN: str = "localhost"
    DEBUG: bool = False
    PORT: int = 80