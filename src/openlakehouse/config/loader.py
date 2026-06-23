import os
from pathlib import Path

import yaml

from openlakehouse.config.models import AppConfig


def load_config(path: str | Path) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return AppConfig.model_validate(raw)


def resolve_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise RuntimeError(f"Required environment variable {var_name} is not set")
    return value
