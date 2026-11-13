from fastapi import Depends, HTTPException, status
from app.users.auth import get_current_user
from app.users.models import User


async def is_admin(current_user: User = Depends(get_current_user),):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен",
        )
    return current_user
