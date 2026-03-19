import os
import re
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    """Load config.yaml, resolving ${ENV_VAR} substitutions."""
    raw = config_path.read_text(encoding="utf-8")

    def replace_env(match):
        var_name = match.group(1)
        value = os.environ.get(var_name, "")
        if not value:
            print(f"[config] Warning: ${var_name} not set in environment")
        return value

    resolved = re.sub(r'\$\{(\w+)\}', replace_env, raw)
    return yaml.safe_load(resolved)
