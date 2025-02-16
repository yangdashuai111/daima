from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.templating import Jinja2Templates
from ..database import get_db
from ..models import Material

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/materials")
async def list_materials(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取素材列表
    result = await db.execute(
        select(Material)
        .order_by(Material.id.desc())
    )
    materials = result.scalars().all()
    
    return templates.TemplateResponse(
        "materials/list.html",
        {
            "request": request,
            "materials": materials
        }
    ) 