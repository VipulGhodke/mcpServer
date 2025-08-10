from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import ExerciseOut, SrsDueResponse
from ..services.srs import due_exercises


router = APIRouter(prefix="/srs", tags=["srs"])


@router.get("/due", response_model=SrsDueResponse)
async def due(user_id: str, limit: int = 20, session: AsyncSession = Depends(get_session)):
    items = await due_exercises(session, user_id, limit)
    await session.commit()
    return SrsDueResponse(exercises=[ExerciseOut.model_validate(e) for e in items])


