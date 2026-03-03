\
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS / SageMaker
    aws_region: str = "us-west-2"
    sagemaker_endpoint: str = ""
    sagemaker_timeout_seconds: int = 5

    # Service behavior
    service_name: str = "service"
    service_version: str = "1.0.0"
    log_level: str = "INFO"

    class Config:
        env_prefix = ""
        case_sensitive = False
