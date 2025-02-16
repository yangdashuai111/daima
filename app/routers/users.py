from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from typing import List
from ..database import get_db
from ..models import User, Track
import re

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 用户管理页面
@router.get("/users")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取所有用户
    result = await db.execute(
        select(User)
        .options(selectinload(User.authorized_tracks))
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    # 获取所有赛道（用于创建用户时选择）
    tracks_result = await db.execute(select(Track))
    tracks = tracks_result.scalars().all()
    
    return templates.TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "users": users,
            "tracks": tracks
        }
    )

# 创建用户
@router.post("/users")
async def create_user(
    phone: str = Form(...),
    password: str = Form(...),
    daily_limit: int = Form(...),
    track_ids: List[int] = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # 验证手机号格式
    if not re.match(r'^1[3-9]\d{9}$', phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    # 检查手机号是否已存在
    result = await db.execute(select(User).where(User.phone == phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 创建新用户
    user = User(
        phone=phone,
        daily_limit=daily_limit
    )
    user.set_password(password)
    
    # 关联赛道
    tracks_result = await db.execute(
        select(Track).where(Track.id.in_(track_ids))
    )
    tracks = tracks_result.scalars().all()
    user.authorized_tracks = tracks
    
    db.add(user)
    await db.commit()
    
    return RedirectResponse(url="/users", status_code=303)

# 删除用户
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "删除成功"} 