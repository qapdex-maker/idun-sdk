"""Async client for the Idun SDK (v0.5).

Thin async wrapper around :mod:`idun.providers`. The underlying HTTP calls
use only the stdlib ``urllib`` (blocking), so the async client runs each
request in a worker thread via :func:`asyncio.to_thread` rather than spinning
up its own thread pool. That keeps the public surface ``async`` for callers
who want concurrent fan-out without blocking the event loop, while the heavy
lifting stays stdlib-only.

Example::

    import asyncio
    from idun.async_client import AsyncIdunClient

    async def main():
        c = AsyncIdunClient()
        results = await asyncio.gather(
            c.acomplete("groq", "hi"),
            c.acomplete("openai", "hi"),
        )
        for r in results:
            print(r.text)

    asyncio.run(main())
"""
from __future__ import annotations

import asyncio

from . import providers as _P
from .providers import (
    Completion, default_provider, get_provider,
)


class AsyncIdunClient:
    """Async counterpart to the synchronous registry calls.

    Every method mirrors a ``idun.providers`` function but is ``async`` and
    never blocks the event loop on the (blocking) urllib transport.
    """

    async def acomplete(self, pid: str, prompt: str, **kwargs) -> Completion:
        """Async version of :func:`idun.providers.complete` (non-streaming)."""
        return await asyncio.to_thread(_P.complete, pid, prompt, **kwargs)

    async def acomplete_chain(self, chain: list[str], prompt: str,
                              **kwargs) -> Completion:
        """Async version of :func:`idun.providers.complete_chain`."""
        return await asyncio.to_thread(_P.complete_chain, chain, prompt, **kwargs)

    @staticmethod
    async def gather(*jobs) -> list:
        """Run several coroutines concurrently and return results in order.

        ``jobs`` are coroutines produced by ``acomplete``/``acomplete_chain``.
        Exceptions propagate (use ``asyncio.gather(..., return_exceptions=True)``
        if you want partial results).
        """
        return await asyncio.gather(*jobs)

    def active_provider(self) -> str:
        """The current default provider id (env / config / azure)."""
        return default_provider()

    def provider(self, pid: str):
        """Return the provider record (raises ValueError if unknown)."""
        return get_provider(pid)


__all__ = ["AsyncIdunClient", "Completion"]
