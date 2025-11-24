from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "PDF Layout Translator"
    VERSION: str = "1.0.0"
    MODEL_REPO_ID: str = "vinai/vinai-translate-en2vi-v2"

Config = Settings()
project_name = Config.PROJECT_NAME
model_repo_id = Config.MODEL_REPO_ID