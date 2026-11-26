from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="XZ_", extra="ignore")

    db_path: Path = Path("data/xianzhi.db")
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-flash"
    webhook_url: str = ""
    # 行情偏离超过该比例时提示"仅公式参考"
    deviation_threshold: float = 0.25

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings()
