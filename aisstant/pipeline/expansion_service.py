"""Background service for generating detailed topic expansions from assistant responses."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from openai import AsyncOpenAI

from aisstant.config import get_api_key

log = logging.getLogger("expansion")

class ExpansionStatus(Enum):
    PENDING = "pending"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True)
class ExpansionResult:
    status: ExpansionStatus
    text: str = ""
    error: str = ""


class ExpansionService:
    """Manages background expansion generation tasks."""

    def __init__(self, model: str, system_prompt: str, user_prompt: str) -> None:
        self._model = model
        self._system_prompt = system_prompt
        self._user_prompt = user_prompt
        self._results: dict[str, ExpansionResult] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._listeners: dict[str, list[Callable[[ExpansionResult], None]]] = {}

    def request_expansion(
        self, block_id: str, response_text: str,
        history: list[dict] | None = None,
    ) -> None:
        """Start a background expansion generation for a response block."""
        self._results[block_id] = ExpansionResult(status=ExpansionStatus.PENDING)
        task = asyncio.create_task(
            self._run_expansion(block_id, response_text, history or []),
        )
        self._tasks[block_id] = task

    def get_result(self, block_id: str) -> ExpansionResult | None:
        return self._results.get(block_id)

    def add_listener(
        self, block_id: str, callback: Callable[[ExpansionResult], None],
    ) -> None:
        self._listeners.setdefault(block_id, []).append(callback)

    def remove_listener(
        self, block_id: str, callback: Callable[[ExpansionResult], None],
    ) -> None:
        listeners = self._listeners.get(block_id, [])
        if callback in listeners:
            listeners.remove(callback)

    async def cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._results.clear()
        self._listeners.clear()

    async def _run_expansion(
        self, block_id: str, response_text: str, history: list[dict],
    ) -> None:
        self._results[block_id] = ExpansionResult(status=ExpansionStatus.LOADING)
        self._notify(block_id)

        try:
            client = AsyncOpenAI(api_key=get_api_key())
            messages: list[dict] = [
                {"role": "system", "content": self._system_prompt},
                *history,
                {
                    "role": "user",
                    "content": self._user_prompt.format(text=response_text),
                },
            ]
            stream = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
            )

            accumulated = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    accumulated += delta
                    self._results[block_id] = ExpansionResult(
                        status=ExpansionStatus.LOADING, text=accumulated,
                    )
                    self._notify(block_id)

            self._results[block_id] = ExpansionResult(
                status=ExpansionStatus.READY, text=accumulated,
            )
            self._notify(block_id)
            log.info("Expansion ready for block %s (%d chars)", block_id, len(accumulated))

        except asyncio.CancelledError:
            log.info("Expansion cancelled for block %s", block_id)
        except Exception as exc:
            log.error("Expansion failed for block %s: %s", block_id, exc)
            self._results[block_id] = ExpansionResult(
                status=ExpansionStatus.ERROR, error=str(exc),
            )
            self._notify(block_id)

    def _notify(self, block_id: str) -> None:
        result = self._results.get(block_id)
        if result is None:
            return
        for callback in self._listeners.get(block_id, []):
            try:
                callback(result)
            except Exception:
                log.exception("Error in expansion listener for block %s", block_id)
