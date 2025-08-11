from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Attempt, Exercise
from ..schemas import (
    ExerciseOut,
    SessionStartRequest,
    SessionStartResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from ..services.gamification import apply_answer_outcome, ensure_user_and_profile
from ..services.grading import grade_answer
from ..services.session_engine import select_session_exercises


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    req: SessionStartRequest, session: AsyncSession = Depends(get_session)
):
    profile = await ensure_user_and_profile(session, req.user_id)
    # Ask for language if not set and not provided
    if not profile.learning_language and not req.learning_language:
        await session.commit()
        return SessionStartResponse(
            exercises=[],
            requires_language_selection=True,
            suggested_languages=["de", "es", "fr", "it"],
        )

    # override learning language if provided
    if req.learning_language:
        profile.learning_language = req.learning_language
    lang = profile.learning_language or "de"
    exercises = await select_session_exercises(session, req.lesson_id, learning_language=lang, profile=profile)
    await session.commit()
    return SessionStartResponse(
        exercises=[ExerciseOut.model_validate(e) for e in exercises],
        requires_language_selection=False,
    )


@router.post("/submit", response_model=SubmitAnswerResponse)
async def submit_answer(
    req: SubmitAnswerRequest, session: AsyncSession = Depends(get_session)
):
    await ensure_user_and_profile(session, req.user_id)
    exercise = await session.get(Exercise, req.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    is_correct, feedback = grade_answer(exercise, req.answer)

    # Persist attempt
    profile = await ensure_user_and_profile(session, req.user_id)
    # Update adaptive difficulty based on correctness
    if is_correct:
        profile.correct_streak += 1
        if profile.correct_streak >= 3:
            profile.current_difficulty = min(5, profile.current_difficulty + 1)
            profile.correct_streak = 0
    else:
        profile.correct_streak = 0
        profile.current_difficulty = max(1, profile.current_difficulty - 1)

    awarded = await apply_answer_outcome(session, profile, is_correct)
    attempt = Attempt(
        user_id=req.user_id,
        exercise_id=req.exercise_id,
        is_correct=is_correct,
        answer=req.answer,
        time_ms=req.time_ms or 0,
        awarded_xp=awarded,
        level=exercise.difficulty,
    )
    session.add(attempt)
    # reload profile to return updated numbers
    profile = await ensure_user_and_profile(session, req.user_id)
    await session.commit()

    return SubmitAnswerResponse(
        is_correct=is_correct,
        awarded_xp=awarded,
        feedback=feedback,
        new_xp=profile.xp,
        hearts=profile.hearts,
        streak_count=profile.streak_count,
    )


