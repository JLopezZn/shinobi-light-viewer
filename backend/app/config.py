import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.footage_dir = Path(os.environ["FOOTAGE_DIR"])
        self.db_path = Path(os.environ["DB_PATH"])
        self.cache_dir = Path(os.environ["CACHE_DIR"])
        self.port: int = int(os.getenv("PORT", "8090"))
        self.scan_interval_seconds: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
        self.shinobi_container: str = os.getenv("SHINOBI_CONTAINER", "shinobi")
        admin_token = os.environ.get("ADMIN_TOKEN", "")
        if not admin_token:
            raise ValueError(
                "ADMIN_TOKEN env var is required. Set it in backend/.env before starting the server."
            )
        self.admin_token: str = admin_token

        if not self.footage_dir.exists():
            raise ValueError(f"FOOTAGE_DIR does not exist: {self.footage_dir}")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
