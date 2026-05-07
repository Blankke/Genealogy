import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


class Settings:
    """集中读取运行配置，便于本地演示和测试环境覆盖。"""

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://genealogy_app:genealogy_password@localhost:5432/genealogy",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    backend_cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "BACKEND_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
