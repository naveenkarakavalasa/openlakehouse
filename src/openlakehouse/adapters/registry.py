from openlakehouse.adapters.aws_adapter import AWSAdapter
from openlakehouse.adapters.databricks_adapter import DatabricksAdapter
from openlakehouse.config.loader import resolve_env
from openlakehouse.config.models import AdapterConfig, AWSAdapterConfig, DatabricksAdapterConfig
from openlakehouse.core.adapter import LakehouseAdapter


def build_adapter(name: str, cfg: AdapterConfig) -> LakehouseAdapter:
    if isinstance(cfg, DatabricksAdapterConfig):
        return DatabricksAdapter(
            name=name,
            host=cfg.host,
            token=resolve_env(cfg.token_env),
            warehouse_http_path=cfg.warehouse_http_path,
        )
    if isinstance(cfg, AWSAdapterConfig):
        return AWSAdapter(
            name=name,
            region=cfg.region,
            catalog_name=cfg.catalog_name,
            athena_output_location=cfg.athena_output_location,
            athena_workgroup=cfg.athena_workgroup,
            profile=cfg.profile,
        )
    raise ValueError(f"Unknown adapter config type: {type(cfg)}")
