from __future__ import annotations

import datetime as dt

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Attempt, Profile, StreakLog, User


DAILY_GOAL_XP = 20
HEARTS_MAX = 5
HEARTS_REGEN_INTERVAL_MINUTES = 15


async def ensure_user_and_profile(session: AsyncSession, user_id: str, *, default_learning_language: str | None = None) -> Profile:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)

    profile = await session.get(Profile, user_id)
    if profile is None:
        profile = Profile(
            user_id=user_id,
            xp=0,
            hearts=HEARTS_MAX,
            streak_count=0,
            learning_language=default_learning_language if default_learning_language else None,
            native_language="en",
        )
        session.add(profile)

    await session.flush()
    return profile


async def update_streak_on_activity(session: AsyncSession, profile: Profile) -> None:
    today = dt.date.today()
    last = profile.last_active
    if last == today:
        return
    if last is None:
        profile.streak_count = 1
    else:
        delta = (today - last).days
        if delta == 1:
            profile.streak_count += 1
        elif delta > 1:
            profile.streak_count = 1
    profile.last_active = today

    exists = await session.scalar(
        select(func.count())
        .select_from(StreakLog)
        .where(and_(StreakLog.user_id == profile.user_id, StreakLog.date == today))
    )
    if not exists:
        session.add(StreakLog(user_id=profile.user_id, date=today))


async def apply_answer_outcome(session: AsyncSession, profile: Profile, is_correct: bool) -> int:
    awarded = 10 if is_correct else 0
    profile.xp += awarded
    if not is_correct:
        profile.hearts = max(0, profile.hearts - 1)
    await update_streak_on_activity(session, profile)
    return awarded


def _compute_hearts_refill(now: dt.datetime, last: dt.datetime | None, current: int) -> tuple[int, dt.datetime]:
    if current >= HEARTS_MAX:
        return current, last or now
    if last is None:
        last = now
    minutes = int((now - last).total_seconds() // 60)
    if minutes <= 0:
        return current, last
    refills = minutes // HEARTS_REGEN_INTERVAL_MINUTES
    if refills <= 0:
        return current, last
    new_hearts = min(HEARTS_MAX, current + refills)
    # advance last by the consumed intervals
    advanced_last = last + dt.timedelta(minutes=refills * HEARTS_REGEN_INTERVAL_MINUTES)
    return new_hearts, advanced_last


async def maybe_regen_hearts(profile: Profile) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    last = profile.hearts_last_refill_at
    if last is not None and last.tzinfo is None:
        # Normalize naive timestamps from sqlite to UTC
        last = last.replace(tzinfo=dt.timezone.utc)
    cur = profile.hearts
    new_hearts, new_last = _compute_hearts_refill(now, last, cur)
    if new_hearts != cur:
        profile.hearts = new_hearts
        profile.hearts_last_refill_at = new_last


async def get_weekly_xp(session: AsyncSession, user_id: str) -> int:
    start = dt.datetime.utcnow() - dt.timedelta(days=7)
    total = await session.scalar(
        select(func.coalesce(func.sum(Attempt.awarded_xp), 0)).where(
            Attempt.user_id == user_id, Attempt.created_at >= start
        )
    )
    return int(total or 0)


