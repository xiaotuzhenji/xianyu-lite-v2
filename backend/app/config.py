import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

class Settings:
    # DB
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "xianyu")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "xianyu123")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "xianyu_lite")

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "xianyu-lite-secret")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

    # Server
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    WEBSOCKET_PORT: int = int(os.getenv("WEBSOCKET_PORT", "8001"))
    SCHEDULER_PORT: int = int(os.getenv("SCHEDULER_PORT", "8002"))

    # Admin
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

settings = Settings()
