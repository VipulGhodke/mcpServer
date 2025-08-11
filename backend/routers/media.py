from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import (
    ImageAnalyzeRequest,
    ImageAnalyzeResponse,
    TranscribeAudioRequest,
    TranscribeAudioResponse,
    MediaEventLogRequest,
)
from ..db import get_session
from ..services.media import analyze_image, transcribe_audio_base64


router = APIRouter(prefix="/media", tags=["media"])


@router.post("/image/analyze", response_model=ImageAnalyzeResponse)
async def image_analyze(req: ImageAnalyzeRequest, user_id: str | None = None, session=Depends(get_session)):
    try:
        width, height, text, notes = await analyze_image(req.image_b64, session=session, user_id=user_id)
        return ImageAnalyzeResponse(width=width, height=height, text=text, notes=notes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")


@router.post("/audio/transcribe", response_model=TranscribeAudioResponse)
async def audio_transcribe(req: TranscribeAudioRequest, user_id: str | None = None, session=Depends(get_session)):
    transcript, confidence, engine = await transcribe_audio_base64(req.audio_b64, req.mime_type, session=session, user_id=user_id)
    return TranscribeAudioResponse(transcript=transcript, confidence=confidence, engine=engine)


@router.post("/event")
async def log_media_event(req: MediaEventLogRequest, session=Depends(get_session)):
    from ..models import MediaEvent
    ev = MediaEvent(user_id=req.user_id, event_type=req.event_type, meta=req.meta)
    session.add(ev)
    await session.commit()
    return {"ok": True, "id": ev.id}


