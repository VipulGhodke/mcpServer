from __future__ import annotations

import base64
import io
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MediaEvent
from PIL import Image

from PIL import Image


def load_image_from_b64(image_b64: str) -> Image.Image:
    data = base64.b64decode(image_b64)
    return Image.open(io.BytesIO(data))


def naive_ocr(image: Image.Image) -> str | None:
    # Placeholder: integrate with pytesseract or PaddleOCR later
    return None


async def analyze_image(image_b64: str, *, session: AsyncSession | None = None, user_id: str | None = None) -> Tuple[int, int, str | None, str | None]:
    img = load_image_from_b64(image_b64)
    width, height = img.size
    text = naive_ocr(img)
    notes = "Image processed. Add OCR/vision model for richer analysis."
    # Record event if session provided
    if session is not None:
        event = MediaEvent(user_id=user_id, event_type="image_analyze", meta={"width": width, "height": height})
        session.add(event)
    return width, height, text, notes


async def transcribe_audio_base64(audio_b64: str, mime_type: str | None = None, *, session: AsyncSession | None = None, user_id: str | None = None) -> tuple[str, float | None, str]:
    # Placeholder: integrate faster-whisper/Cloud STT later
    # For now, return a stub transcript so the flow works end-to-end
    transcript = "<transcription unavailable in stub>"
    confidence = None
    engine = "stub"
    if session is not None:
        event = MediaEvent(user_id=user_id, event_type="audio_transcribe", meta={"mime_type": mime_type or "unknown"})
        session.add(event)
    return transcript, confidence, engine


