"""Idun SDK public API."""
import os

from .client import (IdunClient, IdunResult, Step, _normalize_output,
                     diff_traces, format_diff, Conversation)
from .auth import login, load_token, maybe_refresh
from .prompts import list_packs, load_pack, get_prompt, run_pack
from . import providers, retro
from . import keyring_store
from .providers import (Completion, Provider, complete, get_provider,
                        list_providers, support_matrix, support_matrix_text,
                        estimate_cost, cost_table)

__all__ = ["IdunClient", "IdunResult", "Step", "login", "load_token", "maybe_refresh",
           "_normalize_output", "logo_path", "openapi_path", "list_packs", "load_pack", "get_prompt",
           "diff_traces", "format_diff", "Conversation", "run_pack",
           "providers", "retro", "keyring_store", "Provider", "Completion", "complete",
           "get_provider", "list_providers", "support_matrix", "support_matrix_text",
           "estimate_cost", "cost_table"]
__version__ = "1.0.14"


def logo_path(variant: str = "white") -> str:
    """Path to the bundled Microsoft Foundry logo asset.

    variant: 'white' (Stroke/White, for dark UIs) or 'color' (Color).
    Resolves relative to this package so it works after `pip install`.
    """
    name = "foundry_logo_white.svg" if variant == "white" else "foundry_logo_color.svg"
    return os.path.join(os.path.dirname(__file__), "data", name)


def openapi_path() -> str:
    """Path to the bundled OpenAPI 3 spec describing the completion API.

    Resolves relative to this package so it works after `pip install`.
    """
    return os.path.join(os.path.dirname(__file__), "openapi.json")
