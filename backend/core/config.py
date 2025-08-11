from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    backend_port: int = Field(default=8090, alias="BACKEND_PORT")
    auth_token: Optional[str] = Field(default=None, alias="AUTH_TOKEN")
    # Optional WhatsApp Cloud API config for sending interactive buttons
    whatsapp_token: Optional[str] = Field(default=None, alias="WHATSAPP_TOKEN")
    whatsapp_phone_number_id: Optional[str] = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    facebook_graph_api_version: str = Field(default="v20.0", alias="FACEBOOK_GRAPH_API_VERSION")

    class Config:
        extra = "ignore"


settings = Settings()  # type: ignore[call-arg]


