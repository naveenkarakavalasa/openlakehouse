from typing import Annotated, Literal

from pydantic import BaseModel, Field


class DatabricksAdapterConfig(BaseModel):
    type: Literal["databricks"] = "databricks"
    host: str
    token_env: str
    warehouse_http_path: str


class AWSAdapterConfig(BaseModel):
    type: Literal["aws"] = "aws"
    region: str
    profile: str | None = None
    catalog_name: str = "AwsDataCatalog"
    athena_output_location: str
    athena_workgroup: str | None = None


AdapterConfig = Annotated[
    DatabricksAdapterConfig | AWSAdapterConfig, Field(discriminator="type")
]


class AppConfig(BaseModel):
    policy_path: str = "config/policy.yaml"
    adapters: dict[str, AdapterConfig]
