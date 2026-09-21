from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        extra="ignore",
        populate_by_name=True,
        env_ignore_empty=True,
    )
    dashscope_api_key: SecretStr = SecretStr("")
    # One internal value; the canonical environment name wins over the legacy alias.
    qwen_model: str = Field(default="", validation_alias=AliasChoices("QWEN_CHAT_MODEL", "QWEN_MODEL"))
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    amap_api_key: SecretStr = SecretStr("")
    vite_amap_security_code: SecretStr = SecretStr("")
    vite_amap_js_key: SecretStr = SecretStr("")
    rail_provider: Literal["", "mock", "dataset", "real"] = ""
    rail_api_key: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple:
        def preferred_model() -> dict[str, str]:
            # Resolve names before sources, so an old shell variable cannot mask the canonical .env value.
            for name in ("QWEN_CHAT_MODEL", "QWEN_MODEL"):
                for source in (env_settings, dotenv_settings):
                    key = name if getattr(source, "case_sensitive", False) else name.lower()
                    value = getattr(source, "env_vars", {}).get(key)
                    if isinstance(value, str) and value.strip():
                        return {"QWEN_CHAT_MODEL": value.strip()}
            return {}

        return init_settings, preferred_model, env_settings, dotenv_settings, file_secret_settings

    @property
    def model_ready(self) -> bool:
        return bool(self.dashscope_api_key.get_secret_value() and self.qwen_model)

    @property
    def amap_ready(self) -> bool:
        return bool(self.amap_api_key.get_secret_value())
