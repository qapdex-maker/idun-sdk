"""Idun SDK public API."""
import os

from .client import IdunClient, IdunResult, Step, _normalize_output
from .auth import login, load_token, maybe_refresh

__all__ = ["IdunClient", "IdunResult", "Step", "login", "load_token", "maybe_refresh", "_normalize_output", "logo_path"]
__version__ = "0.1.2"


def logo_path(variant: str = "white") -> str:
    """Path to the bundled Microsoft Foundry logo asset.

    variant: 'white' (Stroke/White, for dark UIs) or 'color' (Color).
    Resolves relative to this package so it works after `pip install`.
    """
    name = "foundry_logo_white.svg" if variant == "white" else "foundry_logo_color.svg"
    return os.path.join(os.path.dirname(__file__), "data", name)
