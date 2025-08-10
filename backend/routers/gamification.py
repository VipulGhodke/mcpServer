from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import GamificationStatus
from ..services.gamification import (
    DAILY_GOAL_XP,
    ensure_user_and_profile,
    get_weekly_xp,
    maybe_regen_hearts,
)


router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/status", response_model=GamificationStatus)
async def status(user_id: str, session: AsyncSession = Depends(get_session)):
    profile = await ensure_user_and_profile(session, user_id)
    # Regenerate hearts before returning status
    await maybe_regen_hearts(profile)
    weekly = await get_weekly_xp(session, user_id)
    await session.commit()
    return GamificationStatus(
        xp=profile.xp,
        hearts=profile.hearts,
        streak_count=profile.streak_count,
        daily_goal_xp=DAILY_GOAL_XP,
        weekly_xp=weekly,
        learning_language=profile.learning_language,
        native_language=profile.native_language,
    )


@router.post("/language")
async def set_learning_language(user_id: str, learning_language: str, session: AsyncSession = Depends(get_session)):
    profile = await ensure_user_and_profile(session, user_id)
    profile.learning_language = learning_language
    await session.flush()
    await session.commit()
    return {"ok": True, "learning_language": profile.learning_language}


