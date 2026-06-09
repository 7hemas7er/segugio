"""Fail-fast config loader (CFG-01).

``load_config(path)`` reads a YAML file with ``yaml.safe_load`` ONLY (never
``yaml.load`` — arbitrary-object deserialization is the classic PyYAML RCE,
threat T-01-02a), validates it into a typed ``Config``, and on ANY read/parse
or validation failure logs the aggregated error via loguru and raises
``SystemExit(2)`` — a malformed config can never reach the live loop (T-01-02b).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger
from pydantic import ValidationError

from .models import Config


def load_config(path: str | Path) -> Config:
    """Load + validate a config file. Fails FAST with a clear, aggregated error.

    Args:
        path: Path to the YAML config file.

    Returns:
        A typed, fully-validated ``Config``.

    Raises:
        SystemExit: With code 2 on any read/parse error or validation failure,
            after logging the aggregated error (CFG-01).
    """
    p = Path(path)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Cannot read/parse config '{p}': {e}")
        raise SystemExit(2) from e
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        logger.error(f"Invalid config '{p}': {e.error_count()} error(s):\n{e}")
        raise SystemExit(2) from e
