from fastapi import APIRouter, Depends, Request, HTTPException, Response, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from jose import jwt
from pydantic import BaseModel
from ..database import get_db
from ..models import User, Article, ArticleClaim, Track, Operator
from ..dependencies import get_current_user, get_current_user_from_cookie
from ..config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 登录请求模型
class LoginRequest(BaseModel):
    phone: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# H5 登录页面
@router.get("/h5/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        "h5/login.html",
        {"request": request}
    )

# H5 登录 API
@router.post("/api/h5/login")
async def login(
    login_data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    # 查找用户
    result = await db.execute(
        select(Operator)
        .where(Operator.phone == login_data.phone)
    )
    operator = result.scalar_one_or_none()
    
    if not operator or not operator.check_password(login_data.password):
        raise HTTPException(
            status_code=401,
            detail="手机号或密码错误"
        )
    
    # 检查审核状态
    if operator.audit_status != "approved":
        raise HTTPException(
            status_code=403,
            detail="账号审核未通过,请等待管理员审核"
        )
    
    # 检查账号状态
    if not operator.status:
        raise HTTPException(
            status_code=403,
            detail="账号已被禁用"
        )
    
    # 更新最后登录时间
    operator.last_login = datetime.now()
    await db.commit()
    
    # 生成 token
    token = create_access_token(
        data={"sub": str(operator.id)}
    )
    
    # 设置 cookie
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    
    return {
        "token": token,
        "token_type": "bearer"
    }

# H5 文章列表页面
@router.get("/h5/articles")
async def article_list(
    request: Request,
    operator: Operator = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    # 获取用户可访问的赛道和文章
    result = await db.execute(
        select(Operator)
        .options(
            selectinload(Operator.managed_tracks).selectinload(Track.articles)
        )
        .where(Operator.id == operator.id)
    )
    operator_with_tracks = result.scalar_one_or_none()
    
    # 获取用户已下载的文章ID
    claimed_result = await db.execute(
        select(ArticleClaim.article_id)
        .where(ArticleClaim.user_id == operator.id)
    )
    claimed_article_ids = [r[0] for r in claimed_result.all()]
    
    return templates.TemplateResponse(
        "h5/articles.html",
        {
            "request": request,
            "user": operator_with_tracks,
            "claimed_article_ids": claimed_article_ids
        }
    )

# 下载文章 API
@router.get("/api/h5/articles/{article_id}/download")
async def download_article(
    article_id: int,
    operator: Operator = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 检查文章是否存在且用户有权限
    result = await db.execute(
        select(Article)
        .where(
            and_(
                Article.id == article_id,
                Article.track_id.in_([t.id for t in operator.managed_tracks])
            )
        )
    )
    article = result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(
            status_code=404,
            detail="文章不存在或无权访问"
        )
    
    # 检查是否已下载过
    claimed_result = await db.execute(
        select(ArticleClaim)
        .where(
            and_(
                ArticleClaim.user_id == operator.id,
                ArticleClaim.article_id == article_id
            )
        )
    )
    if claimed_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="已下载过该文章"
        )
    
    # 检查今日下载数量
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_claims_result = await db.execute(
        select(ArticleClaim)
        .where(
            and_(
                ArticleClaim.user_id == operator.id,
                ArticleClaim.claimed_at >= today_start
            )
        )
    )
    today_claims = today_claims_result.scalars().all()
    
    if len(today_claims) >= operator.daily_limit:
        raise HTTPException(
            status_code=400,
            detail="今日下载数量已达上限"
        )
    
    # 记录下载
    claim = ArticleClaim(
        user_id=operator.id,
        article_id=article_id
    )
    db.add(claim)
    await db.commit()
    
    # 返回文件
    if not os.path.exists(article.file_path):
        raise HTTPException(
            status_code=404,
            detail="文件不存在"
        )
    
    return FileResponse(
        article.file_path,
        filename=f"{article.title}{os.path.splitext(article.file_path)[1]}"
    )

# 赛道文章列表页面
@router.get("/h5/tracks/{track_id}/articles")
async def track_article_list(
    request: Request,
    track_id: int,
    operator: Operator = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    # 检查用户是否有权限访问该赛道
    if track_id not in [t.id for t in operator.managed_tracks]:
        raise HTTPException(
            status_code=403,
            detail="无权访问该赛道"
        )
    
    # 获取赛道信息
    track_result = await db.execute(
        select(Track)
        .where(Track.id == track_id)
    )
    track = track_result.scalar_one_or_none()
    
    if not track:
        raise HTTPException(
            status_code=404,
            detail="赛道不存在"
        )
    
    # 获取赛道下的文章
    result = await db.execute(
        select(Article)
        .where(Article.track_id == track_id)
        .options(selectinload(Article.track))
        .order_by(Article.created_at.desc())
    )
    articles = result.scalars().all()
    
    # 获取用户已下载的文章ID
    claimed_result = await db.execute(
        select(ArticleClaim.article_id)
        .where(ArticleClaim.user_id == operator.id)
    )
    claimed_article_ids = [r[0] for r in claimed_result.all()]
    
    return templates.TemplateResponse(
        "h5/track_articles.html",
        {
            "request": request,
            "user": operator,
            "track": track,
            "articles": articles,
            "claimed_article_ids": claimed_article_ids
        }
    )

# H5 注册申请页面
@router.get("/h5/register")
async def register_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取所有赛道
    result = await db.execute(select(Track))
    tracks = result.scalars().all()
    
    return templates.TemplateResponse(
        "h5/register.html",
        {
            "request": request,
            "tracks": tracks
        }
    )

# H5 注册申请 API
@router.post("/api/h5/register")
async def register(
    track: str = Form(...),
    platform: str = Form(...),
    phone: str = Form(...),
    nickname: str = Form(...),
    account_id: str = Form(...),
    appid: str = Form(...),
    password: str = Form(...),
    register_date: str = Form(...),
    is_violation: str = Form(...),
    screenshot: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 检查手机号是否已存在
    result = await db.execute(
        select(Operator).where(Operator.phone == phone)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="手机号已存在"
        )
    
    # 保存截图
    upload_dir = "static/uploads/screenshots"  # 修改为 static 目录下
    os.makedirs(upload_dir, exist_ok=True)
    file_extension = os.path.splitext(screenshot.filename)[1]
    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"
    file_path = os.path.join(upload_dir, file_name)
    
    with open(file_path, "wb") as f:
        content = await screenshot.read()
        f.write(content)
    
    # 创建代运营账号申请
    operator = Operator(
        username=phone,  # 使用手机号作为用户名
        phone=phone,
        name=nickname,
        platform=platform,
        account_id=account_id,
        appid=appid,
        register_date=datetime.strptime(register_date, "%Y-%m-%d"),
        is_violation=is_violation == "1",
        screenshot_path=file_path.replace("static/", ""),  # 存储相对路径
        audit_status="pending"  # 设置为待审核状态
    )
    operator.set_password(password)
    
    # 关联赛道
    track_result = await db.execute(
        select(Track).where(Track.id == int(track))  # 修改为通过 ID 查找赛道
    )
    track_obj = track_result.scalar_one_or_none()
    if track_obj:
        operator.managed_tracks = [track_obj]
    
    db.add(operator)
    await db.commit()
    
    return {"message": "申请提交成功,请等待审核"}