from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from app.basket.models import BasketItem
from app.database import get_db
from app.orders.models import Order
from app.products.models import Category, Product
from app.store.services import get_shop_settings
from app.users.auth import get_current_user
from app.users.models import User
from app.store.services import get_shop_settings

STORE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(STORE_DIR / "templates" / "store"))

router = APIRouter(tags=["Витрина магазина"])

# Возвращает текущего пользователя из куки
async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    token = request.cookies.get("users_access_token")
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None

# Считает кол. товаров в корзине
async def get_cart_count(user: Optional[User], db: AsyncSession) -> int:
    if not user:
        return 0
    result = await db.execute(
        select(func.coalesce(func.sum(BasketItem.quantity), 0)).where(
            BasketItem.user_id == user.id
        )
    )
    return int(result.scalar() or 0)


@router.get("/", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    sort: str = "newest",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    shop = await get_shop_settings(db)
    categories_res = await db.execute(select(Category).order_by(Category.title))
    categories = categories_res.scalars().all()

    query = select(Product).options(joinedload(Product.category))

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.where(Product.title.ilike(search_term))

    if category_id:
        query = query.where(Product.category_id == category_id)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.id.desc())

    products_res = await db.execute(query)
    products = products_res.scalars().all()

    cart_map: dict[int, int] = {}
    if current_user:
        basket_res = await db.execute(
            select(BasketItem).where(BasketItem.user_id == current_user.id)
        )
        for item in basket_res.scalars().all():
            cart_map[item.product_id] = item.quantity

    cart_count = sum(cart_map.values())

    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "shop": shop,
            "products": products,
            "categories": categories,
            "selected_category_id": category_id,
            "search_query": q or "",
            "sort": sort,
            "current_user": current_user,
            "cart_count": cart_count,
            "cart_map": cart_map,
        },
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail_page(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    shop = await get_shop_settings(db)
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(joinedload(Product.category), selectinload(Product.images))
    )
    res = await db.execute(query)
    product = res.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    in_cart_qty = 0
    if current_user:
        item_res = await db.execute(
            select(BasketItem).where(
                BasketItem.user_id == current_user.id,
                BasketItem.product_id == product_id,
            )
        )
        basket_item = item_res.scalar_one_or_none()
        if basket_item:
            in_cart_qty = basket_item.quantity

    cart_count = await get_cart_count(current_user, db)

    return templates.TemplateResponse(
        request=request,
        name="product.html",
        context={
            "shop": shop,
            "product": product,
            "in_cart_qty": in_cart_qty,
            "current_user": current_user,
            "cart_count": cart_count,
        },
    )


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/cart", status_code=303)

    shop = await get_shop_settings(db)
    query = (
        select(BasketItem)
        .where(BasketItem.user_id == current_user.id)
        .options(joinedload(BasketItem.product))
        .order_by(BasketItem.id.asc())
    )
    res = await db.execute(query)
    basket_items = res.scalars().all()

    items_data = []
    total_price = 0
    total_qty = 0

    for item in basket_items:
        if not item.product:
            continue
        subtotal = item.product.price * item.quantity
        total_price += subtotal
        total_qty += item.quantity
        items_data.append(
            {
                "basket_item_id": item.id,
                "product": item.product,
                "quantity": item.quantity,
                "subtotal": subtotal,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context={
            "shop": shop,
            "items": items_data,
            "total_price": total_price,
            "cart_count": total_qty,
            "current_user": current_user,
        },
    )


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/orders", status_code=303)

    shop = await get_shop_settings(db)
    query = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
        .order_by(Order.id.desc())
    )
    res = await db.execute(query)
    orders = res.scalars().all()

    cart_count = await get_cart_count(current_user, db)

    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={
            "shop": shop,
            "orders": orders,
            "current_user": current_user,
            "cart_count": cart_count,
        },
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    shop = await get_shop_settings(db)
    cart_count = await get_cart_count(current_user, db)
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={
            "shop": shop,
            "current_user": current_user,
            "cart_count": cart_count,
        },
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/profile", status_code=303)

    shop = await get_shop_settings(db)
    cart_count = await get_cart_count(current_user, db)

    orders_res = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
        .order_by(Order.id.desc())
        .limit(5)
    )
    orders = orders_res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "shop": shop,
            "current_user": current_user,
            "cart_count": cart_count,
            "orders": orders,
        },
    )

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "/",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if current_user:
        return RedirectResponse(url=next, status_code=303)
    shop = await get_shop_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "shop": shop,
            "next_url": next,
            "current_user": None,
            "cart_count": 0,
        },
    )

@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    shop = await get_shop_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "shop": shop,
            "current_user": None,
            "cart_count": 0,
        },
    )


@router.get("/logout")
async def logout_user(response: Response):
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie("users_access_token")
    return redirect
