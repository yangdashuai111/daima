from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from jose import jwt, JWTError
from .database import get_db
from .models import Operator
from .config import SECRET_KEY, ALGORITHM

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Operator:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="无效的认证信息"
        )
    
    result = await db.execute(
        select(Operator)
        .options(selectinload(Operator.managed_tracks))
        .where(Operator.id == user_id)
    )
    operator = result.scalar_one_or_none()
    
    if not operator:
        raise HTTPException(
            status_code=401,
            detail="用户不存在"
        )
    
    return operator

# 用于模板页面的认证
async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Operator:
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="未登录"
        )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="无效的认证信息"
        )
    
    result = await db.execute(
        select(Operator)
        .options(selectinload(Operator.managed_tracks))
        .where(Operator.id == user_id)
    )
    operator = result.scalar_one_or_none()
    
    if not operator:
        raise HTTPException(
            status_code=401,
            detail="用户不存在"
        )
    
    return operator 