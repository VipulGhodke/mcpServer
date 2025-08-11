from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    prompt: str
    choices: Optional[list] = None
    difficulty: int


class SessionStartRequest(BaseModel):
    user_id: str
    lesson_id: Optional[str] = None
    learning_language: Optional[str] = None


class SessionStartResponse(BaseModel):
    exercises: List[ExerciseOut]
    requires_language_selection: bool = False
    suggested_languages: List[str] | None = None


class SubmitAnswerRequest(BaseModel):
    user_id: str
    exercise_id: str
    answer: str
    time_ms: Optional[int] = None


class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    awarded_xp: int
    feedback: str
    new_xp: int
    hearts: int
    streak_count: int


class GamificationStatus(BaseModel):
    xp: int
    hearts: int
    streak_count: int
    daily_goal_xp: int
    weekly_xp: int
    learning_language: Optional[str] = None
    native_language: Optional[str] = None


class SrsDueResponse(BaseModel):
    exercises: List[ExerciseOut]


# Media schemas
class ImageAnalyzeRequest(BaseModel):
    image_b64: str


class ImageAnalyzeResponse(BaseModel):
    width: int
    height: int
    text: str | None = None
    notes: str | None = None


class TranscribeAudioRequest(BaseModel):
    audio_b64: str
    mime_type: str | None = None


class TranscribeAudioResponse(BaseModel):
    transcript: str
    confidence: float | None = None
    engine: str | None = None



# Media event logging
class MediaEventLogRequest(BaseModel):
    user_id: Optional[str] = None
    event_type: str
    meta: dict = {}
