from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from typing import List
from ..database import get_db
from ..models import Operator, Track
import re
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 代运营账号管理页面
@router.get("/operators")
async def list_operators(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取所有代运营账号
    result = await db.execute(
        select(Operator)
        .options(selectinload(Operator.managed_tracks))
        .order_by(Operator.created_at.desc())
    )
    operators = result.scalars().all()
    
    # 获取所有赛道（用于创建账号时选择）
    tracks_result = await db.execute(select(Track))
    tracks = tracks_result.scalars().all()
    
    return templates.TemplateResponse(
        "operators/list.html",
        {
            "request": request,
            "operators": operators,
            "tracks": tracks
        }
    )

# 创建代运营账号
@router.post("/operators")
async def create_operator(
    phone: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    daily_limit: int = Form(...),
    track_ids: List[int] = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # 验证手机号格式
    if not re.match(r'^1[3-9]\d{9}$', phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    # 检查手机号是否已存在
    result = await db.execute(select(Operator).where(Operator.phone == phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 创建新账号
    operator = Operator(
        username=phone,  # 使用手机号作为用户名
        name=name,
        phone=phone,
        daily_limit=daily_limit
    )
    operator.set_password(password)
    
    # 关联赛道
    tracks_result = await db.execute(
        select(Track).where(Track.id.in_(track_ids))
    )
    tracks = tracks_result.scalars().all()
    operator.managed_tracks = tracks
    
    db.add(operator)
    await db.commit()
    
    return RedirectResponse(url="/operators", status_code=303)

# 删除代运营账号
@router.delete("/operators/{operator_id}")
async def delete_operator(
    operator_id: int,
    db: AsyncSession = Depends(get_db)
):
    operator = await db.get(Operator, operator_id)
    if not operator:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    await db.delete(operator)
    await db.commit()
    
    return {"message": "删除成功"}

# 审核代运营账号
@router.post("/operators/{operator_id}/audit")
async def audit_operator(
    operator_id: int,
    audit_data: dict,
    db: AsyncSession = Depends(get_db)
):
    operator = await db.get(Operator, operator_id)
    if not operator:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    if operator.audit_status != "pending":
        raise HTTPException(status_code=400, detail="该账号已审核")
    
    operator.audit_status = audit_data.get("audit_status")
    operator.audit_remark = audit_data.get("audit_remark")
    operator.audit_time = datetime.now()
    
    # 如果审核通过，设置账号状态为启用
    if operator.audit_status == "approved":
        operator.status = True
    
    await db.commit()
    return {"message": "审核成功"}

# 获取代运营账号详情
@router.get("/operators/{operator_id}/details")
async def get_operator_details(
    operator_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Operator)
        .options(selectinload(Operator.managed_tracks))
        .where(Operator.id == operator_id)
    )
    operator = result.scalar_one_or_none()
    
    if not operator:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    return {
        "phone": operator.phone,
        "name": operator.name,
        "platform": operator.platform,
        "account_id": operator.account_id,
        "appid": operator.appid,
        "register_date": operator.register_date.strftime("%Y-%m-%d") if operator.register_date else None,
        "is_violation": operator.is_violation,
        "screenshot_path": operator.screenshot_path,
        "audit_status": operator.audit_status,
        "audit_remark": operator.audit_remark,
        "audit_time": operator.audit_time.strftime("%Y-%m-%d %H:%M:%S") if operator.audit_time else None,
        "daily_limit": operator.daily_limit,
        "status": operator.status,
        "managed_tracks": [track.id for track in operator.managed_tracks]
    }

# 编辑代运营账号
@router.post("/operators/{operator_id}/edit")
async def update_operator(
    operator_id: int,
    phone: str = Form(...),
    name: str = Form(...),
    daily_limit: int = Form(...),
    track_ids: List[int] = Form(...),
    status: bool = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # 获取要编辑的账号
    result = await db.execute(
        select(Operator)
        .options(selectinload(Operator.managed_tracks))
        .where(Operator.id == operator_id)
    )
    operator = result.scalar_one_or_none()
    
    if not operator:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    # 如果修改了手机号，检查新手机号是否已存在
    if operator.phone != phone:
        result = await db.execute(
            select(Operator).where(
                and_(
                    Operator.phone == phone,
                    Operator.id != operator_id
                )
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 更新基本信息
    operator.phone = phone
    operator.username = phone  # 用户名同步更新
    operator.name = name
    operator.daily_limit = daily_limit
    operator.status = status
    
    # 更新赛道关联
    tracks_result = await db.execute(
        select(Track).where(Track.id.in_(track_ids))
    )
    tracks = tracks_result.scalars().all()
    operator.managed_tracks = tracks
    
    await db.commit()
    return {"message": "更新成功"} 