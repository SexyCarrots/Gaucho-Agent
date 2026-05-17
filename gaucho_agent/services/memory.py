"""MemoryService – store, retrieve, and conflict-resolve personal facts.

Day 1 ships a transparent heuristic store policy and the type-aware
retrieval scoring from EXPERIMENT_PLAN.md §4.3. The LLM-as-judge store
policy (Day 3-4) plugs into `store()` via the `decider` argument without
changing this interface.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Callable, Optional

from sqlmodel import Session, select

from gaucho_agent.config import settings
from gaucho_agent.models.memory import MemoryItem
from gaucho_agent.services import embeddings

# A store decision. `store=False` means "skip this turn".
StoreDecision = dict
# decider(turn) -> StoreDecision | None
Decider = Callable[[str], Optional[StoreDecision]]

_QUESTION_RE = re.compile(
    r"^\s*(what|when|where|who|why|how|which|can|could|do|does|did|is|are|am|"
    r"should|would|will|may)\b", re.I,
)

# (regex, mem_type, subject_key). First match wins; order = specificity.
_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\ballerg(y|ic|ies)\b", re.I), "profile", "allergy"),
    (re.compile(r"\b(vegetarian|vegan|pescatarian|gluten[- ]?free|lactose|"
                r"dairy[- ]?free|halal|kosher)\b", re.I), "preference", "diet"),
    (re.compile(r"\bi (don'?t |do not )?eat\b|\bi'?m not eating\b", re.I),
     "preference", "diet"),
    (re.compile(r"\bmy name is\b|\bcall me\b|\bi'?m called\b", re.I),
     "profile", "name"),
    (re.compile(r"\bmy major is\b|\bi'?m majoring in\b|\bi'?m a .+ major\b|"
                r"\bi study\b", re.I), "profile", "major"),
    (re.compile(r"\bmy advisor is\b|\bmy (professor|pi)\b", re.I),
     "profile", "advisor"),
    (re.compile(r"\bi live in\b|\bmy dorm\b|\bi'?m staying (at|in)\b|"
                r"\bi'?m from\b", re.I), "profile", "location"),
    (re.compile(r"\bi (have|take) (a |an )?(class|lab|lecture|section|"
                r"discussion)\b|\bmy (lab|class|office hours)\b|\bi work\b|"
                r"\bevery (mon|tue|wed|thu|fri|sat|sun)", re.I),
     "schedule", "schedule"),
    (re.compile(r"\bi'?m planning to\b|\bi plan to\b|\bi'?m going to "
                r"(take|enroll|sign up)\b|\bnext quarter i\b|\bi intend to\b",
                re.I), "plan", "plan"),
    (re.compile(r"\bi (like|love|enjoy|prefer)\b|\bmy favou?rite\b", re.I),
     "preference", "preference"),
    (re.compile(r"\bi (hate|dislike|can'?t stand|don'?t like)\b", re.I),
     "preference", "preference"),
]

_NORMALIZERS = [
    (re.compile(r"^\s*i'?m\b", re.I), "user is"),
    (re.compile(r"^\s*i am\b", re.I), "user is"),
    (re.compile(r"^\s*i\b", re.I), "user"),
    (re.compile(r"\bmy\b", re.I), "user's"),
]


def _normalize_fact(turn: str) -> str:
    """Turn a first-person utterance into a canonical third-person fact."""
    text = turn.strip().rstrip(".!").strip()
    for pat, repl in _NORMALIZERS:
        if pat.search(text):
            text = pat.sub(repl, text, count=1)
            break
    return text[:280]


def heuristic_decider(turn: str) -> Optional[StoreDecision]:
    """Day-1 rule-based store policy. Returns None to skip the turn."""
    t = (turn or "").strip()
    if len(t) < 4 or _QUESTION_RE.match(t) or t.endswith("?"):
        return None
    for pat, mem_type, subject in _PATTERNS:
        if pat.search(t):
            return {
                "store": True,
                "type": mem_type,
                "salient_fact": _normalize_fact(t),
                "subject_key": subject,
                "confidence": 1.0,
            }
    return None


def infer_query_type(query: str) -> str:
    """Best-effort guess of which mem_type a question depends on."""
    q = (query or "").lower()
    if re.search(r"\b(eat|food|dining|menu|lunch|dinner|breakfast|vegetarian|"
                 r"vegan|allerg|restaurant|meal)\b", q):
        return "preference"
    if re.search(r"\b(when|schedule|class|lab|free|busy|time|available|"
                 r"office hours)\b", q):
        return "schedule"
    if re.search(r"\b(name|major|advisor|who am i|where do i live|my dorm)\b", q):
        return "profile"
    if re.search(r"\b(plan|planning|going to take|next quarter|intend)\b", q):
        return "plan"
    return "preference"


class MemoryService:
    """Selective-memory store. One instance per DB session is fine."""

    def __init__(self, decider: Decider | None = None) -> None:
        self._decide = decider or heuristic_decider

    # -- write path ------------------------------------------------------
    def store(
        self,
        session: Session,
        turn: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
        source_turn_idx: int = 0,
    ) -> Optional[MemoryItem]:
        """Decide whether to persist `turn`; supersede stale same-subject facts.

        Returns the new MemoryItem, or None if the policy skipped the turn.
        """
        decision = self._decide(turn)
        if not decision or not decision.get("store"):
            return None

        content = decision.get("salient_fact") or turn.strip()
        item = MemoryItem(
            user_id=user_id,
            session_id=session_id,
            content=content,
            raw_turn=turn.strip(),
            mem_type=decision.get("type", "preference"),
            subject_key=decision.get("subject_key", "misc"),
            created_at=datetime.utcnow(),
            embedding=embeddings.to_bytes(embeddings.embed(content)),
            source_turn_idx=source_turn_idx,
            judge_confidence=float(decision.get("confidence", 1.0)),
        )
        session.add(item)
        session.flush()  # assign item.id before we point supersessions at it
        self.resolve_conflicts(session, item)
        session.commit()
        session.refresh(item)
        return item

    def resolve_conflicts(self, session: Session, new_item: MemoryItem) -> int:
        """Mark older live facts with the same subject_key as superseded.

        Recency-wins override. Returns the number of items superseded.
        """
        rows = session.exec(
            select(MemoryItem).where(
                MemoryItem.user_id == new_item.user_id,
                MemoryItem.subject_key == new_item.subject_key,
                MemoryItem.superseded_by == None,  # noqa: E711
                MemoryItem.id != new_item.id,
            )
        ).all()
        for old in rows:
            old.superseded_by = new_item.id
            session.add(old)
        return len(rows)

    # -- read path -------------------------------------------------------
    def retrieve_scored(
        self,
        session: Session,
        query: str,
        *,
        user_id: str = "default",
        k: int | None = None,
    ) -> list[tuple[MemoryItem, float]]:
        """Return up to k (item, score) pairs, highest score first.

        score = α·cosine + β·type_match + γ·recency_decay  (§4.3)
        Superseded items are excluded.
        """
        k = k if k is not None else settings.mem_top_k
        live = session.exec(
            select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.superseded_by == None,  # noqa: E711
            )
        ).all()
        if not live:
            return []

        q_vec = embeddings.embed(query)
        q_type = infer_query_type(query)
        now = datetime.utcnow()
        a, b, g = settings.mem_alpha, settings.mem_beta, settings.mem_gamma
        tau = max(settings.mem_tau_days, 1e-6)

        scored: list[tuple[MemoryItem, float]] = []
        for m in live:
            sim = embeddings.cosine(q_vec, embeddings.from_bytes(m.embedding))
            type_match = 1.0 if m.mem_type == q_type else 0.0
            age_days = max((now - m.created_at).total_seconds() / 86400.0, 0.0)
            recency = math.exp(-age_days / tau)
            score = a * sim + b * type_match + g * recency
            scored.append((m, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: max(k, 0)]

    def retrieve(
        self,
        session: Session,
        query: str,
        *,
        user_id: str = "default",
        k: int | None = None,
    ) -> list[MemoryItem]:
        return [m for m, _ in self.retrieve_scored(session, query, user_id=user_id, k=k)]
