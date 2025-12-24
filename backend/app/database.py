import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# データベース接続URLの取得
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@db:5432/chatdb")

# 非同期エンジンの作成
engine = create_async_engine(DATABASE_URL, echo=True)

# セッションファクトリの作成
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ベースクラスの作成
Base = declarative_base()

async def get_db():
    """
    データベースセッションを取得する依存関係
    """
    async with SessionLocal() as session:
        yield session
