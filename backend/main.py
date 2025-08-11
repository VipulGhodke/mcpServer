from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import func, select

from .db import get_session, init_db, SessionLocal
from .models import Exercise, Lesson, Skill
from .routers.gamification import router as gamification_router
from .routers.srs import router as srs_router
from .routers.sessions import router as sessions_router
from .routers.media import router as media_router


app = FastAPI(title="Language Learning Backend API")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    # Seed minimal content if empty
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Skill))
        if not count:
            skill = Skill(title="Basics 1", order_index=1)
            session.add(skill)
            await session.flush()

            lesson_es = Lesson(skill_id=skill.id, order_index=1, meta={"lang": "es"}, lang="es")
            session.add(lesson_es)
            await session.flush()

            exs = [
                Exercise(
                    lesson_id=lesson_es.id,
                    type="translate",
                    prompt="Translate: Hello",
                    answer_key="Hola",
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_es.id,
                    type="translate",
                    prompt="Translate: Thank you",
                    answer_key="Gracias",
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_es.id,
                    type="mcq",
                    prompt="Select 'Good morning'",
                    answer_key="Buenos días",
                    choices=["Buenas noches", "Buenos días", "Adiós"],
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_es.id,
                    type="fill_blank",
                    prompt="Fill: ¿Cómo ____?",
                    answer_key="estás",
                    difficulty=2,
                ),
                Exercise(
                    lesson_id=lesson_es.id,
                    type="translate",
                    prompt="Translate: Goodbye",
                    answer_key="Adiós",
                    difficulty=1,
                ),
            ]
            session.add_all(exs)
            # Add a DE lesson with German prompts
            lesson_de = Lesson(skill_id=skill.id, order_index=2, meta={"lang": "de"}, lang="de")
            session.add(lesson_de)
            await session.flush()
            exs_de = [
                Exercise(
                    lesson_id=lesson_de.id,
                    type="translate",
                    prompt="Translate: Good morning",
                    answer_key="Guten Morgen",
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_de.id,
                    type="translate",
                    prompt="Translate: Goodbye",
                    answer_key="Auf Wiedersehen",
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_de.id,
                    type="mcq",
                    prompt="Select 'Hello'",
                    answer_key="Hallo",
                    choices=["Tschüss", "Hallo", "Bitte"],
                    difficulty=1,
                ),
                Exercise(
                    lesson_id=lesson_de.id,
                    type="fill_blank",
                    prompt="Fill: Wie ____ du?",
                    answer_key="heißt",
                    difficulty=2,
                ),
            ]
            session.add_all(exs_de)
            await session.commit()


app.include_router(sessions_router)
app.include_router(gamification_router)
app.include_router(srs_router)
app.include_router(media_router)


@app.get("/health")
async def health():
    return {"status": "ok", "db": True}


