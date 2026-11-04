# config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 1. Объявляем переменные и их типы. 
    # Pydantic сам преобразует строки из .env в bool, int и т.д.
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False  # Можно задать значение по умолчанию
    PORT: int = 8000

    # 2. Указываем Pydantic, откуда читать данные
    model_config = SettingsConfigDict(
        env_file=".env",            # Имя файла
        env_file_encoding="utf-8",  # Кодировка
        extra="ignore"              # Игнорировать лишние переменные в .env, если они есть
    )

# Используем lru_cache, чтобы файл .env читался с диска ровно ОДИН раз
@lru_cache
def get_settings() -> Settings:
    return Settings()

# Создаем один глобальный объект для импорта
settings = get_settings()
