from __future__ import annotations

from difflib import SequenceMatcher

from ..models import Exercise


def _normalize(text: str) -> str:
    return text.strip().lower()


def grade_answer(exercise: Exercise, answer: str) -> tuple[bool, str]:
    """Return (is_correct, feedback_message)."""
    user = answer or ""
    expected = exercise.answer_key or ""

    if exercise.type in {"mcq", "multiple_choice"}:
        raw = user.strip()
        selected_value = raw
        # Map letter options (a/b/c/d) or 1-based indices to choice text
        try:
            choices = exercise.choices or []
        except Exception:
            choices = []
        if len(raw) == 1 and raw.lower() in "abcdefghijklmnopqrstuvwxyz" and choices:
            idx = ord(raw.lower()) - ord("a")
            if 0 <= idx < len(choices):
                selected_value = str(choices[idx])
        elif raw.isdigit() and choices:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                selected_value = str(choices[idx])
        is_correct = _normalize(selected_value) == _normalize(expected)
        return (is_correct, "Correct!" if is_correct else "Incorrect.")

    # Default: text equality with fuzzy hinting
    is_correct = _normalize(user) == _normalize(expected)
    if is_correct:
        return True, "Correct!"

    ratio = SequenceMatcher(None, _normalize(user), _normalize(expected)).ratio()
    if ratio > 0.85:
        return False, "Close! Watch spelling or accents."
    return False, f"Expected: {expected}"


