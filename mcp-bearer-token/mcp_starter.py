import asyncio
from typing import Annotated
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field

import httpx

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8090")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None


# --- MCP Server Setup ---
mcp = FastMCP(
    "ChatLingo MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# @mcp.get("/welcome")
# async def welcome_message():
#     return "Welcome to the MCP Server! Puch ki MKC"

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    return MY_NUMBER




# Image inputs and sending images

MAKE_IMG_BLACK_AND_WHITE_DESCRIPTION = RichToolDescription(
    description="Convert an image to black and white and save it.",
    use_when="Use this tool when the user provides an image URL and requests it to be converted to black and white.",
    side_effects="The image will be processed and saved in a black and white format.",
)

# Removed: black-and-white conversion tool (not needed for ChatLingo)


# --- Duolingo-like tools that proxy to backend API ---
DuolingoToolDescription = RichToolDescription(
    description="ChatLingo tools: start a session, submit an answer, check your daily goals and streak, and review due vocab.",
    use_when="Use to drive a structured language learning flow with XP, hearts, streaks, and adaptive difficulty.",
)


@mcp.tool(description=DuolingoToolDescription.model_dump_json())
async def session_start(
    user_id: Annotated[str, Field(description="User identifier")],
    lesson_id: Annotated[str | None, Field(description="Optional lesson id to focus session on")] = None,
    learning_language: Annotated[str | None, Field(description="Optional target learning language, e.g., 'de', 'es'")] = None,
) -> str:
    async with httpx.AsyncClient() as client:
        payload = {"user_id": user_id, "lesson_id": lesson_id, "learning_language": learning_language}
        resp = await client.post(f"{BACKEND_URL}/sessions/start", json=payload)
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        # Deterministically render the next exercise to avoid upstream hallucinations.
        try:
            data = resp.json()
        except Exception:
            data = None

        # If language selection is required, offer language choices.
        if data and data.get("requires_language_selection"):
            langs = data.get("suggested_languages") or ["de", "es"]
            suggestions = [{"title": f"Learn {l.upper()}", "id": f"set_lang_{l}"} for l in langs[:3]]
            return (
                "Welcome to ChatLingo!\n\n"
                "Here’s how it works:\n"
                "- Earn XP for correct answers and build your streak.\n"
                "- Hearts represent your lives; wrong answers cost a heart. Hearts regenerate over time.\n"
                "- Difficulty adapts to your performance.\n"
                "- You can ask for a Hint, skip with Next, or Quit anytime.\n\n"
                "Please choose a language to learn: " + ", ".join(langs) + "\n\n"
                + f"<suggested_replies>{suggestions}</suggested_replies>"
            )

        # Render a single exercise prompt (first item) in plain text with embedded metadata
        # so the chat layer does not invent alternate prompts.
        if not data or not isinstance(data, dict):
            # Fallback to original body if parsing failed
            suggestions = [
                {"title": "Next", "id": "next_ex"},
                {"title": "Hint", "id": "hint"},
                {"title": "Quit", "id": "quit"},
            ]
            return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"

        exercises = data.get("exercises") or []
        if not exercises:
            suggestions = [
                {"title": "Next", "id": "next_ex"},
                {"title": "Quit", "id": "quit"},
            ]
            return (
                "You're all caught up for now. No exercises available.\n\n"
                + f"<suggested_replies>{suggestions}</suggested_replies>"
            )

        ex = exercises[0]
        ex_id = ex.get("id") or ""
        ex_type = ex.get("type") or "text"
        prompt = ex.get("prompt") or ""
        choices = ex.get("choices") or []

        # Normalize some common prompt patterns for readability
        human_prompt = prompt
        if isinstance(prompt, str) and prompt.lower().startswith("translate:"):
            # Show the quoted phrase cleanly
            phrase = prompt.split(":", 1)[1].strip()
            human_prompt = (
                "Translate the following into the target language:\n\n" f"\"{phrase}\""
            )
        elif ex_type in ("mcq", "multiple_choice") and choices:
            options = "\n".join([f"- {c}" for c in choices])
            human_prompt = f"{prompt}\n\nChoose one:\n{options}"

        # Suggestions for conversation flow
        suggestions = [
            {"title": "Next", "id": "next_ex"},
            {"title": "Hint", "id": "hint"},
            {"title": "Quit", "id": "quit"},
        ]

        # Embed machine-readable exercise metadata to keep state stable upstream
        meta = {"exercise_id": ex_id, "type": ex_type}
        instructions = "\n\nReply with your answer only (e.g., the word/phrase or 'a'/'b'/'c' for choices). It will be graded and your XP will update."
        return (
            human_prompt
            + instructions
            + "\n\n"
            + f"<exercise_meta>{meta}</exercise_meta>"
            + "\n\n"
            + f"<suggested_replies>{suggestions}</suggested_replies>"
        )


# --- Media tools ---
@mcp.tool(description="Analyze a user-provided image (base64) for OCR/metadata; returns suggested replies.")
async def image_analyze(
    puch_image_data: Annotated[str, Field(description="Base64-encoded image to analyze")],
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/media/image/analyze",
            json={"image_b64": puch_image_data},
        )
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        suggestions = [
            {"title": "Next", "id": "next"},
            {"title": "Explain", "id": "explain"},
            {"title": "Try another", "id": "try_another"},
        ]
        # Also record an explicit media event for traceability
        try:
            _ = await client.post(f"{BACKEND_URL}/media/event", json={"event_type": "image_analyze_tool", "meta": {"size": len(puch_image_data)}})
        except Exception:
            pass
        return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"


@mcp.tool(description="Transcribe a voice note (base64 audio) and return text with suggested actions.")
async def transcribe_audio(
    puch_audio_data: Annotated[str, Field(description="Base64-encoded audio data")],
    mime_type: Annotated[str | None, Field(description="Optional audio MIME type e.g. audio/ogg")]=None,
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/media/audio/transcribe",
            json={"audio_b64": puch_audio_data, "mime_type": mime_type},
        )
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        suggestions = [
            {"title": "Play again", "id": "play_again"},
            {"title": "Slower", "id": "slower"},
            {"title": "Next", "id": "next"},
        ]
        try:
            _ = await client.post(f"{BACKEND_URL}/media/event", json={"event_type": "audio_transcribe_tool", "meta": {"size": len(puch_audio_data), "mime_type": mime_type}})
        except Exception:
            pass
        return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"


@mcp.tool(description="Submit an answer for grading and XP/streak updates via backend")
async def submit_answer(
    user_id: Annotated[str, Field(description="User identifier")],
    exercise_id: Annotated[str, Field(description="Exercise id")],
    answer: Annotated[str, Field(description="User's answer")],
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/sessions/submit",
            json={"user_id": user_id, "exercise_id": exercise_id, "answer": answer},
        )
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        # Render a strict, backend-driven feedback message to avoid interpretation errors
        try:
            data = resp.json()
        except Exception:
            data = None

        if not data or not isinstance(data, dict):
            # Fallback to raw response
            suggestions = [
                {"title": "Next", "id": "next_ex"},
                {"title": "Explain", "id": "explain"},
                {"title": "Repeat", "id": "repeat"},
            ]
            return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"

        is_correct = bool(data.get("is_correct"))
        feedback = data.get("feedback") or ("Correct!" if is_correct else "Incorrect.")
        awarded = data.get("awarded_xp")
        hearts = data.get("hearts")
        streak = data.get("streak_count")

        if is_correct:
            parts = ["Correct! 🎉"]
            if isinstance(awarded, int) and awarded > 0:
                parts.append(f"+{awarded} XP")
        else:
            parts = [feedback]
        summary = " ".join(parts)

        # Provide follow-up actions as suggested replies
        suggestions = [
            {"title": "Next", "id": "next_ex"},
            {"title": "Explain", "id": "explain"},
            {"title": "Repeat", "id": "repeat"},
        ]

        # Include minimal machine-readable result meta
        meta = {"correct": is_correct, "awarded_xp": awarded, "hearts": hearts, "streak": streak}
        return (
            summary
            + "\n\n"
            + f"<result_meta>{meta}</result_meta>"
            + "\n\n"
            + f"<suggested_replies>{suggestions}</suggested_replies>"
        )


@mcp.tool(description="Fetch daily goals and gamification status (xp, hearts, streak, quests)")
async def gamification_status(
    user_id: Annotated[str, Field(description="User identifier")],
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/gamification/status", params={"user_id": user_id})
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        suggestions = [
            {"title": "Daily goal", "id": "daily_goal"},
            {"title": "Start session", "id": "start_session"},
            {"title": "Due cards", "id": "due_cards"},
        ]
        return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"


@mcp.tool(description="Get due SRS vocab items for the user")
async def srs_due(
    user_id: Annotated[str, Field(description="User identifier")],
    limit: Annotated[int | None, Field(description="Optional limit of due items")] = 20,
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/srs/due", params={"user_id": user_id, "limit": limit})
        if resp.status_code >= 400:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Backend error: {resp.text}"))
        suggestions = [
            {"title": "Start review", "id": "start_review"},
            {"title": "Skip", "id": "skip"},
            {"title": "Back", "id": "back"},
        ]
        return resp.text + "\n\n" + f"<suggested_replies>{suggestions}</suggested_replies>"

# --- Run MCP Server ---
async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
