from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import router

app = FastAPI()

# CORS設定
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# スタティックファイルのマウント (アップロード画像用)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # テーブルの作成
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "help-support-chat-backend"}

app.include_router(router, prefix="/api")
