"""Few-shot prompt for the LLM-as-judge store policy.

The judge sees one user turn and decides whether it contains a durable
personal fact worth remembering. Output is the strict JSON contract from
EXPERIMENT_PLAN.md §4.2. PROMPT_VERSION is part of the cache key — bump it
whenever this prompt changes so stale cached judgements are invalidated.
"""

from __future__ import annotations

PROMPT_VERSION = "v1"

_CONTRACT = """Return ONLY a JSON object with exactly these keys:
{
  "store": boolean,            // true only for durable, user-specific facts
  "type": "preference" | "profile" | "schedule" | "plan",
  "salient_fact": string,      // canonical 3rd-person fact, e.g. "user is vegetarian"
  "subject_key": string,       // stable override bucket: diet, allergy, name,
                               //   major, advisor, location, schedule, plan, ...
  "confidence": number,        // 0..1
  "supersedes": string|null    // describe prior fact this overrides, else null
}
Store ONLY personal facts about THIS user that stay true across sessions
(diet, allergies, name, major, advisor, recurring schedule, stable
preferences, concrete plans). Do NOT store questions, small talk,
one-off transient state, or facts about other people/the world."""

_EXAMPLES = [
    ("I'm vegetarian",
     '{"store": true, "type": "preference", "salient_fact": "user is '
     'vegetarian", "subject_key": "diet", "confidence": 0.96, '
     '"supersedes": null}'),
    ("Actually I eat chicken now, not fully veggie anymore",
     '{"store": true, "type": "preference", "salient_fact": "user eats '
     'chicken (no longer vegetarian)", "subject_key": "diet", '
     '"confidence": 0.9, "supersedes": "prior diet preference (vegetarian)"}'),
    ("I have a peanut allergy",
     '{"store": true, "type": "profile", "salient_fact": "user has a peanut '
     'allergy", "subject_key": "allergy", "confidence": 0.98, '
     '"supersedes": null}'),
    ("My lab meets every Tuesday at 2pm in Phelps",
     '{"store": true, "type": "schedule", "salient_fact": "user has lab '
     'every Tuesday 2pm in Phelps", "subject_key": "schedule", '
     '"confidence": 0.92, "supersedes": null}'),
    ("I'm planning to take CS291A next quarter",
     '{"store": true, "type": "plan", "salient_fact": "user plans to take '
     'CS291A next quarter", "subject_key": "plan", "confidence": 0.85, '
     '"supersedes": null}'),
    ("What dining commons are open right now?",
     '{"store": false, "type": "preference", "salient_fact": "", '
     '"subject_key": "", "confidence": 0.97, "supersedes": null}'),
    ("thanks, that was helpful!",
     '{"store": false, "type": "preference", "salient_fact": "", '
     '"subject_key": "", "confidence": 0.99, "supersedes": null}'),
    ("My friend Sam is allergic to shellfish",
     '{"store": false, "type": "profile", "salient_fact": "", '
     '"subject_key": "", "confidence": 0.88, "supersedes": null}'),
]


def system_prompt() -> str:
    shots = "\n".join(
        f'Turn: {t}\nJSON: {j}' for t, j in _EXAMPLES
    )
    return (
        "You are a memory-curation judge for a personal academic assistant.\n"
        f"{_CONTRACT}\n\nExamples:\n{shots}\n"
    )


def build_messages(turn: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": f"Turn: {turn}\nJSON:"},
    ]
