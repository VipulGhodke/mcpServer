from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Exercise, Lesson, Profile


async def select_session_exercises(
    session: AsyncSession, lesson_id: str | None, limit: int = 5, learning_language: str | None = None, profile: Profile | None = None
):
    if lesson_id:
        stmt = (
            select(Exercise)
            .where(Exercise.lesson_id == lesson_id)
            .order_by(func.random())
            .limit(limit)
        )
    else:
        if learning_language:
            # find lessons matching language either in json meta or in lang column
            lesson_ids_stmt = select(Lesson.id).where(
                (Lesson.lang == learning_language) | (Lesson.meta["lang"].as_string() == learning_language)
            )
            if profile is not None:
                target = max(1, min(5, profile.current_difficulty))
                stmt = (
                    select(Exercise)
                    .where(Exercise.lesson_id.in_(lesson_ids_stmt))
                    .order_by(func.abs(Exercise.difficulty - target), func.random())
                    .limit(limit)
                )
            else:
                stmt = (
                    select(Exercise)
                    .where(Exercise.lesson_id.in_(lesson_ids_stmt))
                    .order_by(func.random())
                    .limit(limit)
                )
        else:
            stmt = select(Exercise).order_by(func.random()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


