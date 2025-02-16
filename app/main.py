from fastapi import FastAPI, Request # type: ignore
from fastapi.staticfiles import StaticFiles # type: ignore
from fastapi.templating import Jinja2Templates # type: ignore
from .database import init_db
from .routers import accounts, materials, content, users, h5, operators

app = FastAPI(title="公众号矩阵管理系统")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板配置
templates = Jinja2Templates(directory="app/templates")

# 注册路由
app.include_router(accounts.router)
app.include_router(materials.router)
app.include_router(content.router)
app.include_router(users.router)
app.include_router(h5.router)
app.include_router(operators.router)

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    ) 