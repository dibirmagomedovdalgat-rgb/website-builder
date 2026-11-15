import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy import delete
from app.database import AsyncSessionLocal
from app.products.models import TempUpload



BASE_DIR = Path(__file__).resolve().parents[2]  # Корневая папка проекта
TEMP_DIR = (BASE_DIR / "img" / "temp").resolve()  # Полный путь к временной папке
MAX_RAW_FILE_SIZE = 20 * 1024 * 1024  # Максимальный размер файла
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}  # Какие форматы файлов разрешены по заголовку
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}  # Разрешенные реальные форматы картинок
ALLOWED_EXTENSIONS = {".webp"}  # Разрешенное расширение после конвертации
MAX_IMAGE_SIZE = (1024, 1024)  # Разрешение фото


# Валидация фото
def validate_and_process_image(file: UploadFile):
    # Проверка формата по заголовку
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не является валидным изображением (разрешены JPG, PNG, WEBP)."
        )
    
    # Проверка веса файла
    if file.size and file.size > MAX_RAW_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл слишком большой для обработки."
        )
    
    try:
        # Открытие файла через pillow
        image = Image.open(file.file)
        
        # Проверка формата файла
        if image.format not in ALLOWED_PIL_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неподдерживаемый формат изображения."
            )
        
        # Проверка если с ориентацией картинки что-то не так
        if hasattr(image, '_getexif') and image._getexif() is not None:  # Если данные о ориентации есть
            image = ImageOps.exif_transpose(image)  # Нормальная ориентация 
            
        # Уменьшение картинки что б она вписалась в квадрат 1024x1024
        image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        return image
    except HTTPException:
        raise
    except Exception:  # Если что-то пошло не так
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать изображение. Возможно, файл поврежден."
        )


def get_verified_temp_file(filename: str):
    safe_name = Path(filename).name # Имя файла
    # Если расширение файла не подходит
    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимое расширение файла."
        )

    target_path = (TEMP_DIR / safe_name).resolve() # Полный путь до файла

    # Проверка что файл лежит внутри TEMP_DIR и является он файлом а не папкой
    if not target_path.is_relative_to(TEMP_DIR) or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Временный файл не найден или доступ к нему запрещен."
        )
    return target_path

# Удаляет файлы которые загрузили но не реализовали
async def clean_expired_temp_files():
    if TEMP_DIR.exists():
        current_time = time.time()
        max_age_seconds = 24 * 3600  # Перевод 24 часа в секунды 
        for file_path in TEMP_DIR.iterdir():  # Цикл по всем файлам внутри img/temp
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime  # Возраст файла
                # Если лежит больше 24 часов то это мусор
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()  # Удаление файла с диска
                        print(f"удален заброшенный файл {file_path.name}")
                    except Exception as e:
                        print(f"Ошибка удаления файла {file_path.name}: {e}")

    # Удалиение мусорных записей
    expiration_time = datetime.now(timezone.utc) - timedelta(hours=24)
    async with AsyncSessionLocal() as session:
        query = delete(TempUpload).where(TempUpload.created_at < expiration_time) # Запрос на удаление всех записей которые лежат там больше 24 часов
        await session.execute(query)
        await session.commit()




