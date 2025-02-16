from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import get_db
from ..models import Track, Article
import os
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 赛道管理页面
@router.get("/tracks")
async def list_tracks(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 使用 selectinload 预加载 articles 关系
    result = await db.execute(
        select(Track)
        .options(selectinload(Track.articles))
        .order_by(Track.created_at.desc())
    )
    tracks = result.scalars().all()
    return templates.TemplateResponse(
        "content/tracks.html",
        {
            "request": request,
            "tracks": tracks
        }
    )

# 创建赛道
@router.post("/tracks")
async def create_track(
    name: str = Form(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    track = Track(name=name, description=description)
    db.add(track)
    await db.commit()
    return RedirectResponse(url="/tracks", status_code=303)

# 文章管理页面
@router.get("/articles")
async def list_articles(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 获取所有赛道
    tracks_result = await db.execute(select(Track))
    tracks = tracks_result.scalars().all()
    
    # 获取所有文章
    articles_result = await db.execute(
        select(Article).order_by(Article.created_at.desc())
    )
    articles = articles_result.scalars().all()
    
    return templates.TemplateResponse(
        "content/articles.html",
        {
            "request": request,
            "tracks": tracks,
            "articles": articles
        }
    )

# 上传文章
@router.post("/articles")
async def create_article(
    title: str = Form(...),
    track_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 创建上传目录
    upload_dir = "static/uploads/articles"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成文件名
    file_extension = os.path.splitext(file.filename)[1]
    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"
    file_path = os.path.join(upload_dir, file_name)
    
    # 保存文件
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 创建文章记录
    article = Article(
        title=title,
        track_id=track_id,
        file_path=file_path
    )
    db.add(article)
    await db.commit()
    
    return RedirectResponse(url="/articles", status_code=303)

# 删除赛道
@router.delete("/tracks/{track_id}")
async def delete_track(
    track_id: int,
    db: AsyncSession = Depends(get_db)
):
    # 删除赛道
    await db.execute(delete(Track).where(Track.id == track_id))
    await db.commit()
    return JSONResponse(content={"message": "删除成功"}) 