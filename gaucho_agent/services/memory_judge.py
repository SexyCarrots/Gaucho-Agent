"""LLM-as-judge store policy with turn-hash caching.

`MemoryJudge.judge(turn)` returns the strict JSON contract from
EXPERIMENT_PLAN.md §4.2. Calls are cached in the `llm_cache` table keyed
by hash(model, prompt, prompt_version) so re-runs are free.

Offline behaviour: with no OpenAI key and no injected `complete_fn`, the
judge degrades to the Day-1 heuristic mapped into the contract, so the
test suite and demos run with no network.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

import httpx
from sqlmodel import Session

from gaucho_agent.config import settings
from gaucho_agent.models.memory import MEMORY_TYPES
from gaucho_agent.prompts import memory_judge as prompt
from gaucho_agent.services import llm_cache
from gaucho_agent.services.memory import StoreDecision, heuristic_decider

CompleteFn = Callable[[list[dict]], str]

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_JSON_RE = re.compile(r"\{.*\}", re.S)


def _openai_complete(messages: list[dict], model: str) -> str:
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_OPENAI_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


def _coerce(raw: dict, turn: str) -> StoreDecision:
    """Validate/repair a parsed judge dict into the contract."""
    store = bool(raw.get("store", False))
    mem_type = raw.get("type")
    if mem_type not in MEMORY_TYPES:
        mem_type = "preference"
    fact = (raw.get("salient_fact") or "").strip()
    subject = (raw.get("subject_key") or "").strip() or "misc"
    try:
        conf = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    conf = min(max(conf, 0.0), 1.0)
    if store and not fact:
        store = False
    return {
        "store": store,
        "type": mem_type,
        "salient_fact": fact,
        "subject_key": subject if store else "",
        "confidence": conf,
        "supersedes": raw.get("supersedes") or None,
    }


def _heuristic_contract(turn: str) -> StoreDecision:
    """Map the Day-1 heuristic into the judge contract (offline fallback)."""
    d = heuristic_decider(turn)
    if not d:
        return {
            "store": False, "type": "preference", "salient_fact": "",
            "subject_key": "", "confidence": 0.7, "supersedes": None,
        }
    return {
        "store": True,
        "type": d["type"],
        "salient_fact": d["salient_fact"],
        "subject_key": d["subject_key"],
        "confidence": float(d.get("confidence", 0.7)),
        "supersedes": None,
    }


class MemoryJudge:
    def __init__(
        self,
        complete_fn: CompleteFn | None = None,
        model: str | None = None,
        offline: bool | None = None,
    ) -> None:
        self._model = model or settings.memory_judge_model
        if offline is None:
            # auto: offline if no key and no injected completion fn
            offline = complete_fn is None and not settings.openai_api_key
        self._offline = offline
        self._complete = complete_fn or (
            lambda msgs: _openai_complete(msgs, self._model)
        )

    @property
    def offline(self) -> bool:
        return self._offline

    def judge(self, turn: str, session: Session | None = None) -> StoreDecision:
        turn = (turn or "").strip()
        if not turn:
            return _coerce({}, turn)
        if self._offline:
            return _heuristic_contract(turn)

        messages = prompt.build_messages(turn)
        key = llm_cache.make_key(
            self._model,
            messages[0]["content"] + "\x00" + turn,
            prompt.PROMPT_VERSION,
        )
        if session is not None:
            cached = llm_cache.get_cached(session, key)
            if cached is not None:
                return self._parse(cached, turn)

        text = self._complete(messages)
        if session is not None:
            llm_cache.put_cache(session, key, self._model, text)
        return self._parse(text, turn)

    def _parse(self, text: str, turn: str) -> StoreDecision:
        try:
            return _coerce(json.loads(text), turn)
        except (json.JSONDecodeError, TypeError):
            m = _JSON_RE.search(text or "")
            if m:
                try:
                    return _coerce(json.loads(m.group(0)), turn)
                except json.JSONDecodeError:
                    pass
        # Unparseable model output -> safe heuristic fallback.
        return _heuristic_contract(turn)


def judge_decider(
    session: Session | None = None,
    judge: MemoryJudge | None = None,
):
    """Return a MemoryService-compatible decider backed by the judge.

    The session is captured so judgements are cached per turn-hash.
    """
    j = judge or MemoryJudge()

    def _decide(turn: str) -> Optional[StoreDecision]:
        return j.judge(turn, session=session)

    return _decide
