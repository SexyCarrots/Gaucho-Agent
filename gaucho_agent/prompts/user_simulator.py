"""Adversarial user personas for EXP-3 (EXPERIMENT_PLAN.md §7.3).

Used both as LLM system prompts (when a key is present) and as the spec
for the deterministic offline conversation transforms in
`scripts/simulate_user.py`.
"""

from __future__ import annotations

PERSONAS = {
    "contradictory": (
        "You frequently change your mind. Mention a preference, then "
        "explicitly contradict it 1-2 sessions later. Vary how you signal "
        "the change ('actually...', 'I lied earlier...', 'now I prefer...')."
    ),
    "distractor": (
        "You bury one important fact ('I have a peanut allergy') among 10 "
        "throwaway personal details ('I like the color blue', 'my dorm "
        "faces east'). Test whether the agent extracts signal from noise."
    ),
    "paraphraser": (
        "When asking memory-dependent questions later, never use the same "
        "wording you used when introducing the fact. Synonyms, indirect "
        "references, different grammatical framings."
    ),
}

PERSONA_NAMES = tuple(PERSONAS)
