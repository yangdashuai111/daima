from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.templating import Jinja2Templates
from ..database import get_db
from ..models import Account, Browser

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/accounts")
async def list_accounts(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取账号列表
    result = await db.execute(select(Account).order_by(Account.id))
    accounts = result.scalars().all()
    
    # 获取浏览器列表
    browser_result = await db.execute(select(Browser).order_by(Browser.id))
    browsers = browser_result.scalars().all()
    
    return templates.TemplateResponse(
        "accounts/list.html",
        {
            "request": request,
            "accounts": accounts,
            "browsers": browsers
        }
    ) 