from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

# Для того что б не дублировать в коде что у каждой картинки есть путь
class ProductImageBase(BaseModel):
    image_path: str

# Схема изображения которая возвращается
class ProductImageResponse(ProductImageBase):
#   image_path: str
    id: int # Id изображения
    product_id: int # Id продукта
    model_config = ConfigDict(from_attributes=True) # Режим совместимости с SQLAlchemy


# Для того что б не дублировать код
class ProductBase(BaseModel):
    title: str # Название товара
    description: Optional[str] = None # Описание товара
    price: int # Цена товара
    quantity: int # Колличество товара
    category_id: int #Id категории


# Схема товара котоая возвращается. Уже хранит title, description и price т.к. наследуетсчя от ProductBase
class ProductResponse(ProductBase):
#   title: str # Название товара
#   description: Optional[str] = None # Описание товара
#   price: int # Цена товара
#   quantity: int # Колличество товара
    id: int # Id товара
    preview_image: Optional[str] = None # Путь к превью
    images: List[ProductImageResponse] = [] # Список объектов, в объекте хранится id фото, путь к фото, id продукта
    model_config = ConfigDict(from_attributes=True)

# Схема для информации на карточке продукта
class ProductShortResponse(ProductBase):
#   title: str # Название товара
#   description: Optional[str] = None # Описание товара
#   price: int # Цена товара
#   quantity: int # Колличество товара
    id: int
    preview_image: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# Используется внутри ProductCreate. Клиент передает ТОЛЬКО image_path.
class ProductImageCreate(ProductImageBase):
    pass


# Схема для создания продукта
class ProductCreate(ProductBase):
#   title: str # Название товара
#   description: Optional[str] = None # Описание товара
#   price: int # Цена товара
#   quantity: int # Колличество товара
    preview_image: Optional[str] = None    # Путь к главной фотографии карточки
    images: List[ProductImageCreate] = []  # Список картинок

# Схема для создания категории
class CategoryCreate(BaseModel):
    title: str # Название


# Схема для категории которвя возвращает Id и название категории
class CategoryResponse(BaseModel):
    id: int # ID
    title: str # Название
    model_config = ConfigDict(from_attributes=True)

class TempUploadResponse(BaseModel):
    upload_id: str

class ProductImageCreate(BaseModel):
    upload_id: str = Field(..., min_length=36, max_length=36)

class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: int
    quantity: int
    category_id: Optional[int] = None
    preview_upload_id: Optional[str] = Field(None, min_length=36, max_length=36)
    images: List[ProductImageCreate] = []
