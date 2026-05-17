"""Helpers around the LLMCache table: deterministic key + get/put."""

from __future__ import annotations

import hashlib

from sqlmodel import Session, select

from gaucho_agent.models.llm_cache import LLMCache


def make_key(model: str, prompt: str, version: str = "v1") -> str:
    h = hashlib.sha256()
    h.update(f"{version}\x00{model}\x00{prompt}".encode("utf-8"))
    return h.hexdigest()


def get_cached(session: Session, key: str) -> str | None:
    row = session.get(LLMCache, key)
    if row is None:
        return None
    row.hit_count += 1
    session.add(row)
    session.commit()
    return row.response


def put_cache(session: Session, key: str, model: str, response: str) -> None:
    existing = session.get(LLMCache, key)
    if existing is not None:
        return
    session.add(LLMCache(cache_key=key, model=model, response=response))
    session.commit()


def cache_size(session: Session) -> int:
    return len(session.exec(select(LLMCache)).all())
