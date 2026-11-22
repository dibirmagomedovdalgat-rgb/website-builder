import re
import shutil
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote
from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, Response)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.products.models import Category, Product, ProductImage, TempUpload
from app.products.routers import (
    create_category as api_create_category,
    create_product as api_create_product,
    delete_category as api_delete_category,
    upload_gallery_file as api_upload_gallery,
    upload_preview_file as api_upload_preview,
)
from app.users.auth import get_current_user, get_or_create_csrf_token, verify_csrf
from app.products.schemas import CategoryCreate, ProductCreate
from app.products.services import (BASE_DIR as PRODUCTS_BASE_DIR, clean_expired_temp_files, get_verified_temp_file,)
from app.users.services import is_admin
from app.store.services import get_shop_settings


router = APIRouter(prefix="/admin",tags=["Admin"],dependencies=[Depends(get_current_user), Depends(is_admin), Depends(verify_csrf)],)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def redirect_with_msg(msg: str) -> RedirectResponse:
    return RedirectResponse(url=f"/admin?msg={quote(msg)}", status_code=303)

# Главная страница админки
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    response: Response,
    msg: Optional[str] = None,
    q: Optional[str] = None,
    cat_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):

    csrf_token = get_or_create_csrf_token(request, response)
    query = (
        select(Product)
        .options(selectinload(Product.category))
        .order_by(Product.id.desc())
    )

    search_query = q.strip() if q else ""
    if search_query:
        query = query.where(Product.title.ilike(f"%{search_query}%"))

    selected_cat_id = int(cat_id) if cat_id and cat_id.isdigit() else None
    if selected_cat_id is not None:
        query = query.where(Product.category_id == selected_cat_id)

    products_result = await db.execute(query)
    products = products_result.scalars().all()
    categories_result = await db.execute(select(Category).order_by(Category.title))
    categories = categories_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "products": products,
            "categories": categories,
            "msg": msg,
            "q": search_query,
            "selected_cat_id": selected_cat_id,
            "csrf_token": csrf_token,
        },
        headers=dict(response.headers),
    )


# Создание товара
@router.post("/products/create")
async def admin_create_product(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    description: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    preview_file: Optional[UploadFile] = File(None),
    gallery_files: List[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        preview_upload_id = None
        if preview_file and preview_file.filename:
            res = await api_upload_preview(
                file=preview_file, current_user=current_user, db=db
            )
            preview_upload_id = res["upload_id"]

        gallery_items = []
        for g_file in gallery_files:
            if g_file and g_file.filename:
                res = await api_upload_gallery(
                    file=g_file, current_user=current_user, db=db
                )
                gallery_items.append({"upload_id": res["upload_id"]})

        cat_id = int(category_id) if category_id and category_id.isdigit() else None
        product_schema = ProductCreate(
            title=title.strip(),
            price=price,
            quantity=quantity,
            description=description.strip() if description and description.strip() else None,
            category_id=cat_id,
            preview_upload_id=preview_upload_id,
            images=gallery_items if gallery_items else None,
        )

        await api_create_product(
            product_data=product_schema,
            background_tasks=background_tasks,
            current_user=current_user,
            db=db,
        )
        return redirect_with_msg("Товар успешно добавлен")

    except HTTPException as exc:
        return redirect_with_msg(f"Ошибка: {exc.detail}")
    
# Редактирование товара
@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def admin_edit_product_page(
    request: Request,
    response: Response,
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    csrf_token = get_or_create_csrf_token(request, response)
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    categories_result = await db.execute(select(Category).order_by(Category.title))
    categories = categories_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="admin/edit_product.html",
        context={
            "product": product,
            "categories": categories,
            "csrf_token": csrf_token,
        },
        headers=dict(response.headers),
    )


# Сохранение изменений товара и фотографий
@router.post("/products/{product_id}/edit")
async def admin_update_product(
    product_id: int,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    price: int = Form(...),
    quantity: int = Form(...),
    description: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    remove_preview: Optional[str] = Form(None),
    delete_image_ids: List[int] = Form(default=[]),
    preview_file: Optional[UploadFile] = File(None),
    gallery_files: List[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    try:
        product.title = title.strip()
        product.price = price
        product.quantity = quantity
        product.description = description.strip() if description and description.strip() else None
        product.category_id = int(category_id) if category_id and category_id.isdigit() else None

        has_new_preview = bool(preview_file and preview_file.filename)
        if (remove_preview == "1" or has_new_preview) and product.preview_image:
            old_preview = PRODUCTS_BASE_DIR / product.preview_image
            if old_preview.exists():
                old_preview.unlink()
            product.preview_image = None

        if has_new_preview:
            res = await api_upload_preview(
                file=preview_file, current_user=current_user, db=db
            )
            rec_res = await db.execute(
                select(TempUpload).where(TempUpload.id == res["upload_id"])
            )
            temp_rec = rec_res.scalar_one()
            temp_path = get_verified_temp_file(temp_rec.filename)

            final_dir = PRODUCTS_BASE_DIR / "img" / "previews"
            final_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_path), str(final_dir / temp_path.name))

            product.preview_image = f"img/previews/{temp_path.name}"
            await db.delete(temp_rec)

        if delete_image_ids:
            for img in list(product.images):
                if img.id in delete_image_ids:
                    img_path = PRODUCTS_BASE_DIR / img.image_path
                    if img_path.exists():
                        img_path.unlink()
                    await db.delete(img)

        final_gallery_dir = PRODUCTS_BASE_DIR / "img" / "gallery"
        for g_file in gallery_files:
            if g_file and g_file.filename:
                res = await api_upload_gallery(
                    file=g_file, current_user=current_user, db=db
                )
                rec_res = await db.execute(
                    select(TempUpload).where(TempUpload.id == res["upload_id"])
                )
                temp_rec = rec_res.scalar_one()
                temp_path = get_verified_temp_file(temp_rec.filename)

                final_gallery_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(final_gallery_dir / temp_path.name))

                product.images.append(
                    ProductImage(image_path=f"img/gallery/{temp_path.name}")
                )
                await db.delete(temp_rec)

        await db.commit()
        background_tasks.add_task(clean_expired_temp_files)
        return redirect_with_msg("Товар и фотографии обновлены")

    except HTTPException as exc:
        return redirect_with_msg(f"Ошибка: {exc.detail}")


# Детальный просмотр товара
@router.get("/products/{product_id}", response_class=HTMLResponse)
async def admin_product_detail(
    request: Request,
    response: Response,
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    csrf_token = get_or_create_csrf_token(request, response)
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.images),
            selectinload(Product.category),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return templates.TemplateResponse(
        request=request,
        name="admin/product_detail.html",
        context={
            "product": product,
            "csrf_token": csrf_token,
        },
        headers=dict(response.headers),
    )



# Удаление товара
@router.post("/products/{product_id}/delete")
async def admin_delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id).options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if product:
        if product.preview_image:
            p_path = PRODUCTS_BASE_DIR / product.preview_image
            if p_path.exists():
                p_path.unlink()
        for img in product.images:
            g_path = PRODUCTS_BASE_DIR / img.image_path
            if g_path.exists():
                g_path.unlink()
        await db.delete(product)
        await db.commit()
    return redirect_with_msg("Товар удалён")



# Создание категории
@router.post("/categories/create")
async def admin_create_category(
    title: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        cat_schema = CategoryCreate(title=title.strip())
        await api_create_category(category_data=cat_schema, db=db)
        return redirect_with_msg("Категория создана")
    except HTTPException as exc:
        return redirect_with_msg(f"Ошибка: {exc.detail}")


# Удаление категории
@router.post("/categories/{category_id}/delete")
async def admin_delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await api_delete_category(category_id=category_id, db=db)
        return redirect_with_msg("Категория удалена")
    except HTTPException as exc:
        return redirect_with_msg(f"Ошибка: {exc.detail}")


STORE_STATIC_DIR = Path(__file__).resolve().parent.parent / "store" / "static"

def get_available_themes() -> list[str]:
    if not STORE_STATIC_DIR.exists():
        return ["default.css"]
    themes = sorted(f.name for f in STORE_STATIC_DIR.glob("*.css") if f.is_file())
    return themes or ["default.css"]


# Страница настроек витрины магазина
@router.get("/shop-settings", response_class=HTMLResponse)
async def shop_settings_page(
    request: Request,
    response: Response,
    msg: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    csrf_token = get_or_create_csrf_token(request, response)
    shop = await get_shop_settings(db)
    themes = get_available_themes()

    return templates.TemplateResponse(
        request=request,
        name="admin/shop_settings.html",
        context={
            "shop": shop,
            "themes": themes,
            "msg": msg,
            "csrf_token": csrf_token,
        },
        headers=dict(response.headers),
    )


# Сохранение настроек витрины магазина и загрузка CSS
@router.post("/shop-settings")
async def update_shop_settings(
    name: str = Form(...),
    slogan: Optional[str] = Form(None),
    about_text: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    work_hours: Optional[str] = Form(None),
    social_link: Optional[str] = Form(None),
    theme_css: str = Form("default.css"),
    custom_css_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    shop = await get_shop_settings(db)

    shop.name = name.strip() or "Мой магазин"
    shop.slogan = slogan.strip() if slogan and slogan.strip() else None
    shop.about_text = about_text.strip() if about_text and about_text.strip() else None
    shop.phone = phone.strip() if phone and phone.strip() else None
    shop.address = address.strip() if address and address.strip() else None
    shop.work_hours = work_hours.strip() if work_hours and work_hours.strip() else None
    shop.social_link = social_link.strip() if social_link and social_link.strip() else None

    available_themes = get_available_themes()
    selected_theme = theme_css if theme_css in available_themes else "default.css"

    if custom_css_file and custom_css_file.filename:
        raw_name = Path(custom_css_file.filename).name
        if not raw_name.lower().endswith(".css"):
            return RedirectResponse(
                url=f"/admin/shop-settings?msg={quote('Ошибка: можно загружать только файлы с расширением .css')}",
                status_code=303,
            )

        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(raw_name).stem) or "custom_theme"
        safe_filename = f"{safe_stem}.css"

        content = await custom_css_file.read()
        if len(content) > 2 * 1024 * 1024:
            return RedirectResponse(
                url=f"/admin/shop-settings?msg={quote('Ошибка: размер CSS-файла не должен превышать 2 МБ')}",
                status_code=303,
            )

        STORE_STATIC_DIR.mkdir(parents=True, exist_ok=True)
        (STORE_STATIC_DIR / safe_filename).write_bytes(content)
        selected_theme = safe_filename

    shop.theme_css = selected_theme
    await db.commit()

    return RedirectResponse(
        url=f"/admin/shop-settings?msg={quote('Настройки магазина и тема сохранены')}",
        status_code=303,
    )

@router.post("/shop-settings/themes/delete")
async def delete_shop_theme(
    theme_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    safe_name = Path(theme_name).name

    # Запрет на удаление дефолтного css
    if safe_name == "default.css" or not safe_name.lower().endswith(".css"):
        return RedirectResponse(
            url=f"/admin/shop-settings?msg={quote('Ошибка: стандартную тему default.css удалить нельзя')}",
            status_code=303,
        )

    target_file = (STORE_STATIC_DIR / safe_name).resolve()

    if target_file.parent != STORE_STATIC_DIR.resolve() or not target_file.is_file():
        return RedirectResponse(
            url=f"/admin/shop-settings?msg={quote('Файл темы не найден')}",
            status_code=303,
        )

    target_file.unlink()

    # Если удалили активный css то поставится  default.css
    shop = await get_shop_settings(db)
    if shop.theme_css == safe_name:
        shop.theme_css = "default.css"
        await db.commit()

    return RedirectResponse(
        url=f"/admin/shop-settings?msg={quote(f'Тема {safe_name} удалена')}",
        status_code=303,
    )