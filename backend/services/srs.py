from __future__ import annotations

import datetime as dt
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Attempt, Exercise


def _compute_streak(attempts: list[Attempt]) -> int:
    streak = 0
    for att in attempts:
        if att.is_correct:
            streak += 1
        else:
            break
    return streak


async def due_exercises(
    session: AsyncSession, user_id: str, limit: int = 20
) -> List[Exercise]:
    # naive MVP: compute due date per exercise based on last attempts
    result = await session.execute(select(Exercise))
    all_exercises = list(result.scalars().all())

    today = dt.date.today()
    due_list: list[Exercise] = []

    for ex in all_exercises:
        attempts_result = await session.execute(
            select(Attempt)
                .where(Attempt.user_id == user_id, Attempt.exercise_id == ex.id)
                .order_by(Attempt.created_at.desc())
                .limit(10)
        )
        attempts = list(attempts_result.scalars().all())
        if not attempts:
            due_list.append(ex)
            continue

        # compute correct streak from most recent backwards
        streak = _compute_streak(attempts)
        interval_days = min(32, 2 ** max(0, streak))  # 1,2,4,8,16,32
        last_date = attempts[0].created_at.date()
        due_date = last_date + dt.timedelta(days=interval_days)
        if due_date <= today:
            due_list.append(ex)

        if len(due_list) >= limit:
            break

    if len(due_list) < limit:
        # pad with others
        for ex in all_exercises:
            if ex not in due_list:
                due_list.append(ex)
                if len(due_list) >= limit:
                    break

    return due_list[:limit]


