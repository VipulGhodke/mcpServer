import asyncio
from typing import Annotated
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field, AnyUrl

import markdownify
import httpx
import readabilipy

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

print(TOKEN)
print(MY_NUMBER)
assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"


# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(
            public_key=k.public_key, jwks_uri=None, issuer=None, audience=None
        )
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


# --- Fetch Utility Class ---
class Fetch:
    USER_AGENT = "Puch/1.0 (Autonomous)"

    @classmethod
    async def fetch_url(
        cls,
        url: str,
        user_agent: str,
        force_raw: bool = False,
    ) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={"User-Agent": user_agent},
                    timeout=30,
                )
            except httpx.HTTPError as e:
                raise McpError(
                    ErrorData(
                        code=INTERNAL_ERROR, message=f"Failed to fetch {url}: {e!r}"
                    )
                )

            if response.status_code >= 400:
                raise McpError(
                    ErrorData(
                        code=INTERNAL_ERROR,
                        message=f"Failed to fetch {url} - status code {response.status_code}",
                    )
                )

            page_raw = response.text

        content_type = response.headers.get("content-type", "")
        is_page_html = "text/html" in content_type

        if is_page_html and not force_raw:
            return cls.extract_content_from_html(page_raw), ""

        return (
            page_raw,
            f"Content type {content_type} cannot be simplified to markdown, but here is the raw content:\n",
        )

    @staticmethod
    def extract_content_from_html(html: str) -> str:
        """Extract and convert HTML content to Markdown format."""
        ret = readabilipy.simple_json.simple_json_from_html_string(
            html, use_readability=True
        )
        if not ret or not ret.get("content"):
            return "<error>Page failed to be simplified from HTML</error>"
        content = markdownify.markdownify(ret["content"], heading_style=markdownify.ATX)
        return content

    @staticmethod
    async def google_search_links(query: str, num_results: int = 5) -> list[str]:
        """
        Perform a scoped DuckDuckGo search and return a list of job posting URLs.
        (Using DuckDuckGo because Google blocks most programmatic scraping.)
        """
        ddg_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        links = []

        async with httpx.AsyncClient() as client:
            resp = await client.get(ddg_url, headers={"User-Agent": Fetch.USER_AGENT})
            if resp.status_code != 200:
                return ["<error>Failed to perform search.</error>"]

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", class_="result__a", href=True):
            href = a["href"]
            if "http" in href:
                links.append(href)
            if len(links) >= num_results:
                break

        return links or ["<error>No results found.</error>"]


# --- MCP Server Setup ---
mcp = FastMCP(
    "Language Learning MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# @mcp.get("/welcome")
# async def welcome_message():
#     return "Welcome to the MCP Server! Puch ki MKC"


# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    return MY_NUMBER


# --- Tool: language_learning_assistant (smart language learning!) ---
LanguageLearningDescription = RichToolDescription(
    description="Smart language learning tool: translate text, provide grammar explanations, find learning resources, and practice exercises.",
    use_when="Use this to help with language learning, translation, grammar questions, or finding learning materials.",
    side_effects="Returns translations, grammar explanations, learning resources, or practice exercises.",
)


@mcp.tool(description=LanguageLearningDescription.model_dump_json())
async def language_learning_assistant(
    user_query: Annotated[
        str,
        Field(
            description="The user's language learning request (translation, grammar question, practice request, etc.)"
        ),
    ],
    target_language: Annotated[
        str | None,
        Field(
            description="Target language for translation or learning (e.g., 'Spanish', 'French', 'Japanese')"
        ),
    ] = None,
    source_text: Annotated[
        str | None, Field(description="Text to translate or analyze")
    ] = None,
    difficulty_level: Annotated[
        str | None,
        Field(description="Difficulty level: 'beginner', 'intermediate', 'advanced'"),
    ] = None,
) -> str:
    """
    Handles multiple language learning tasks: translation, grammar help, practice exercises, and resource finding.
    """
    query_lower = user_query.lower()

    # Translation requests
    if any(
        word in query_lower for word in ["translate", "translation", "how do you say"]
    ):
        if not source_text or not target_language:
            return "🔤 **Translation Request**\n\nPlease provide both the text to translate and the target language.\n\nExample: 'Translate \"Hello, how are you?\" to Spanish'"

        # Simulate translation (in a real implementation, you'd use a translation API)
        return (
            f"🔤 **Translation: {source_text} → {target_language}**\n\n"
            f"**Original:** {source_text}\n"
            f"**Translation:** [Translation would appear here]\n\n"
            f"💡 **Grammar Notes:**\n"
            f"- Word order differences\n"
            f"- Cultural context considerations\n"
            f"- Common usage patterns"
        )

    # Grammar help
    elif any(
        word in query_lower
        for word in ["grammar", "conjugate", "tense", "verb", "noun", "adjective"]
    ):
        return (
            f"📚 **Grammar Help: {user_query}**\n\n"
            f"**Explanation:**\n"
            f"- Grammar rule explanation\n"
            f"- Examples of correct usage\n"
            f"- Common mistakes to avoid\n\n"
            f"**Practice Tip:** Try using this grammar point in 3 different sentences."
        )

    # Practice exercises
    elif any(word in query_lower for word in ["practice", "exercise", "quiz", "test"]):
        level = difficulty_level or "beginner"
        return (
            f"🎯 **Practice Exercise ({level} level)**\n\n"
            f"**Exercise:** Complete the following sentences:\n"
            f"1. [Fill in the blank exercise]\n"
            f"2. [Multiple choice question]\n"
            f"3. [Translation exercise]\n\n"
            f"**Instructions:** Take your time and think about the grammar rules we've discussed."
        )

    # Learning resources
    elif any(
        word in query_lower
        for word in ["resource", "learn", "study", "material", "book", "app"]
    ):
        return (
            f"📖 **Learning Resources for {target_language or 'Language Learning'}**\n\n"
            f"**Recommended Apps:**\n"
            f"- Duolingo (free)\n"
            f"- Memrise (vocabulary focus)\n"
            f"- HelloTalk (language exchange)\n\n"
            f"**Online Resources:**\n"
            f"- YouTube channels for {target_language or 'your target language'}\n"
            f"- Grammar websites\n"
            f"- Podcasts for learners\n\n"
            f"**Practice Tips:**\n"
            f"- Set daily goals (15-30 minutes)\n"
            f"- Practice speaking with native speakers\n"
            f"- Watch movies/TV shows with subtitles"
        )

    # General language learning advice
    else:
        return (
            f"🌍 **Language Learning Assistant**\n\n",
            f"**Your Query:** {user_query}\n\n",
            f"**How I can help you:**\n",
            f"• Translate text between languages\n",
            f"• Explain grammar rules and concepts\n",
            f"• Provide practice exercises\n",
            f"• Recommend learning resources\n",
            f"• Help with pronunciation and vocabulary\n\n",
            f"**Try asking:**\n",
            f"- 'Translate \"Hello\" to Spanish'\n",
            f"- 'Explain past tense in French'\n",
            f"- 'Give me a practice exercise for beginners'\n",
            f"- 'Find resources to learn Japanese'",
        )


# --- Tool: vocabulary_practice (vocabulary learning!) ---
VocabularyPracticeDescription = RichToolDescription(
    description="Create vocabulary practice sessions with flashcards, word lists, and quizzes.",
    use_when="Use this to practice vocabulary, create flashcards, or test knowledge of words in a target language.",
    side_effects="Returns vocabulary exercises, flashcards, or word lists for practice.",
)


@mcp.tool(description=VocabularyPracticeDescription.model_dump_json())
async def vocabulary_practice(
    target_language: Annotated[
        str,
        Field(
            description="Target language for vocabulary practice (e.g., 'Spanish', 'French', 'Japanese')"
        ),
    ],
    category: Annotated[
        str | None,
        Field(
            description="Vocabulary category (e.g., 'food', 'animals', 'colors', 'numbers', 'greetings')"
        ),
    ] = None,
    difficulty: Annotated[
        str | None,
        Field(description="Difficulty level: 'beginner', 'intermediate', 'advanced'"),
    ] = None,
    practice_type: Annotated[
        str | None,
        Field(
            description="Type of practice: 'flashcards', 'quiz', 'word_list', 'fill_blank'"
        ),
    ] = None,
) -> str:
    """
    Creates vocabulary practice materials for language learning.
    """
    level = difficulty or "beginner"
    vocab_type = practice_type or "flashcards"
    vocab_category = category or "common words"

    if vocab_type == "flashcards":
        return (
            f"🃏 **Vocabulary Flashcards - {target_language} ({level})**\n\n"
            f"**Category:** {vocab_category}\n\n"
            f"**Flashcards:**\n"
            f"1. **English:** Hello\n   **{target_language}:** [Translation]\n\n"
            f"2. **English:** Thank you\n   **{target_language}:** [Translation]\n\n"
            f"3. **English:** Goodbye\n   **{target_language}:** [Translation]\n\n"
            f"**Practice Tip:** Cover the {target_language} word and try to remember it!"
        )

    elif vocab_type == "quiz":
        return (
            f"🧠 **Vocabulary Quiz - {target_language} ({level})**\n\n"
            f"**Category:** {vocab_category}\n\n"
            f"**Questions:**\n"
            f"1. How do you say 'Hello' in {target_language}?\n"
            f"   A) [Option A]\n"
            f"   B) [Option B]\n"
            f"   C) [Option C]\n\n"
            f"2. What does '[Word]' mean in English?\n"
            f"   A) [Option A]\n"
            f"   B) [Option B]\n"
            f"   C) [Option C]\n\n"
            f"**Instructions:** Choose the best answer for each question."
        )

    elif vocab_type == "word_list":
        return (
            f"📝 **Word List - {target_language} ({level})**\n\n"
            f"**Category:** {vocab_category}\n\n"
            f"**Essential Words:**\n"
            f"• Hello - [Translation]\n"
            f"• Goodbye - [Translation]\n"
            f"• Thank you - [Translation]\n"
            f"• Please - [Translation]\n"
            f"• Yes - [Translation]\n"
            f"• No - [Translation]\n\n"
            f"**Study Tip:** Practice these words daily for better retention!"
        )

    else:  # fill_blank
        return (
            f"✏️ **Fill in the Blank - {target_language} ({level})**\n\n"
            f"**Category:** {vocab_category}\n\n"
            f"**Exercises:**\n"
            f"1. 'Hello' in {target_language} is: _____\n"
            f"2. The {target_language} word for 'thank you' is: _____\n"
            f"3. 'Goodbye' translates to: _____\n\n"
            f"**Instructions:** Fill in the missing {target_language} words."
        )


# Image processing tools

MAKE_IMG_BLACK_AND_WHITE_DESCRIPTION = RichToolDescription(
    description="Convert an image to black and white and save it.",
    use_when="Use this tool when the user provides an image URL and requests it to be converted to black and white.",
    side_effects="The image will be processed and saved in a black and white format.",
)


@mcp.tool(description=MAKE_IMG_BLACK_AND_WHITE_DESCRIPTION.model_dump_json())
async def make_img_black_and_white(
    puch_image_data: Annotated[
        str,
        Field(description="Base64-encoded image data to convert to black and white"),
    ] = None,
) -> list[TextContent | ImageContent]:
    import base64
    import io

    from PIL import Image

    try:
        image_bytes = base64.b64decode(puch_image_data)
        image = Image.open(io.BytesIO(image_bytes))

        bw_image = image.convert("L")

        buf = io.BytesIO()
        bw_image.save(buf, format="PNG")
        bw_bytes = buf.getvalue()
        bw_base64 = base64.b64encode(bw_bytes).decode("utf-8")

        return [ImageContent(type="image", mimeType="image/png", data=bw_base64)]
    except Exception as e:
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))


# --- Tool: image_processor (comprehensive image processing) ---
IMAGE_PROCESSOR_DESCRIPTION = RichToolDescription(
    description="Process images with various effects: resize, rotate, apply filters, adjust brightness/contrast, and more.",
    use_when="Use this tool for any image processing task like resizing, rotating, filtering, or adjusting image properties.",
    side_effects="Returns the processed image with the requested modifications applied.",
)


@mcp.tool(description=IMAGE_PROCESSOR_DESCRIPTION.model_dump_json())
async def image_processor(
    puch_image_data: Annotated[
        str, Field(description="Base64-encoded image data to process")
    ],
    operation: Annotated[
        str,
        Field(
            description="Image operation: 'resize', 'rotate', 'blur', 'sharpen', 'brightness', 'contrast', 'sepia', 'vintage'"
        ),
    ],
    width: Annotated[
        int | None, Field(description="New width for resize operation")
    ] = None,
    height: Annotated[
        int | None, Field(description="New height for resize operation")
    ] = None,
    angle: Annotated[
        float | None, Field(description="Rotation angle in degrees")
    ] = None,
    intensity: Annotated[
        float | None, Field(description="Effect intensity (0.0 to 2.0, 1.0 = normal)")
    ] = 1.0,
) -> list[TextContent | ImageContent]:
    """
    Comprehensive image processing tool with multiple operations.
    """
    import base64
    import io
    from PIL import Image, ImageFilter, ImageEnhance

    try:
        # Decode image
        image_bytes = base64.b64decode(puch_image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Apply requested operation
        if operation == "resize":
            if width and height:
                processed_image = image.resize(
                    (width, height), Image.Resampling.LANCZOS
                )
            else:
                return [
                    TextContent(
                        type="text",
                        text="❌ Resize operation requires both width and height parameters.",
                    )
                ]

        elif operation == "rotate":
            if angle is not None:
                processed_image = image.rotate(angle, expand=True, fillcolor="white")
            else:
                return [
                    TextContent(
                        type="text",
                        text="❌ Rotate operation requires angle parameter.",
                    )
                ]

        elif operation == "blur":
            radius = max(0.1, min(10.0, intensity * 2))
            processed_image = image.filter(ImageFilter.GaussianBlur(radius=radius))

        elif operation == "sharpen":
            factor = max(0.0, min(3.0, intensity))
            enhancer = ImageEnhance.Sharpness(image)
            processed_image = enhancer.enhance(factor)

        elif operation == "brightness":
            factor = max(0.1, min(3.0, intensity))
            enhancer = ImageEnhance.Brightness(image)
            processed_image = enhancer.enhance(factor)

        elif operation == "contrast":
            factor = max(0.1, min(3.0, intensity))
            enhancer = ImageEnhance.Contrast(image)
            processed_image = enhancer.enhance(factor)

        elif operation == "sepia":
            # Convert to sepia tone
            processed_image = image.convert("RGB")
            pixels = processed_image.load()
            for i in range(processed_image.width):
                for j in range(processed_image.height):
                    r, g, b = pixels[i, j]
                    tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                    tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                    tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                    pixels[i, j] = (min(255, tr), min(255, tg), min(255, tb))

        elif operation == "vintage":
            # Apply vintage effect (sepia + vignette)
            processed_image = image.convert("RGB")
            # Apply sepia first
            pixels = processed_image.load()
            for i in range(processed_image.width):
                for j in range(processed_image.height):
                    r, g, b = pixels[i, j]
                    tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                    tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                    tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                    pixels[i, j] = (min(255, tr), min(255, tg), min(255, tb))

            # Reduce contrast slightly for vintage look
            enhancer = ImageEnhance.Contrast(processed_image)
            processed_image = enhancer.enhance(0.8)

        else:
            return [
                TextContent(
                    type="text",
                    text=f"❌ Unknown operation: {operation}. Available operations: resize, rotate, blur, sharpen, brightness, contrast, sepia, vintage",
                )
            ]

        # Convert processed image to base64
        buf = io.BytesIO()
        processed_image.save(buf, format="PNG")
        processed_bytes = buf.getvalue()
        processed_base64 = base64.b64encode(processed_bytes).decode("utf-8")

        return [
            TextContent(
                type="text",
                text=f"✅ **Image processed successfully!**\n\n**Operation:** {operation.title()}\n**Status:** Complete",
            ),
            ImageContent(type="image", mimeType="image/png", data=processed_base64),
        ]

    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Image processing failed: {str(e)}")
        )


# --- Tool: duolingo_assistant (interactive language practice) ---
DuolingoAssistantDescription = RichToolDescription(
    description="Provides interactive, Duolingo-style language practice exercises like translations, quizzes, and fill-in-the-blank questions.",
    use_when="Use this tool to generate interactive practice exercises for a target language on a specific topic.",
    side_effects="Returns a structured language exercise for the user to complete.",
)


@mcp.tool(description=DuolingoAssistantDescription.model_dump_json())
async def duolingo_assistant(
    target_language: Annotated[
        str,
        Field(
            description="The target language for the exercise (e.g., 'Spanish', 'French')"
        ),
    ],
    topic: Annotated[
        str | None,
        Field(
            description="The topic for the exercise (e.g., 'food', 'greetings', 'travel')"
        ),
    ] = None,
    exercise_type: Annotated[
        str,
        Field(
            description="The type of exercise to generate: 'translation', 'multiple_choice', 'fill_in_the_blank'"
        ),
    ] = "translation",
) -> str:
    """
    Generates a Duolingo-style language practice exercise.
    """
    if exercise_type == "translation":
        return (
            f"🎯 **Translation Exercise: {target_language.title()} ({topic or 'General'})**\n\n"
            f"**Translate the following sentence to {target_language.title()}:**\n"
            f"'I would like to have a coffee.'\n\n"
            f"**Your Answer:** _______"
        )

    elif exercise_type == "multiple_choice":
        return (
            f"🧠 **Multiple Choice Quiz: {target_language.title()} ({topic or 'General'})**\n\n"
            f"**Question:** Which is the correct word for 'water' in {target_language.title()}?\n"
            f"A) [Option A]\n"
            f"B) [Option B]\n"
            f"C) [Option C]\n\n"
            f"**Your Answer:** _______"
        )

    elif exercise_type == "fill_in_the_blank":
        return (
            f"✏️ **Fill in the Blank: {target_language.title()} ({topic or 'General'})**\n\n"
            f"**Complete the following sentence:**\n"
            f"I have a ____ (cat) in my house.\n\n"
            f"**Your Answer:** _______"
        )

    else:
        return (
            f"❌ **Error:** Unknown exercise type '{exercise_type}'. "
            f"Please choose from 'translation', 'multiple_choice', or 'fill_in_the_blank'."
        )


# --- Tool: interactive_language_tutor (fun and interactive learning) ---
InteractiveLanguageTutorDescription = RichToolDescription(
    description="A fun and interactive language tutor that provides flashcards, quizzes, and roleplay conversation practice.",
    use_when="Use this tool when the user wants to do fun practice exercises, flashcards, quizzes, or roleplay a conversation.",
    side_effects="Returns an interactive learning exercise or starts a conversation with the user.",
)


@mcp.tool(description=InteractiveLanguageTutorDescription.model_dump_json())
async def interactive_language_tutor(
    target_language: Annotated[
        str,
        Field(
            description="The language for the practice exercise (e.g., 'Spanish', 'French', 'Japanese')"
        ),
    ],
    topic: Annotated[
        str | None,
        Field(
            description="The topic or theme for the exercise (e.g., 'travel', 'food', 'greetings')"
        ),
    ] = None,
    mode: Annotated[
        str,
        Field(
            description="The type of practice: 'flashcards', 'quiz', 'roleplay', 'fun_practice'"
        ),
    ] = "fun_practice",
) -> str:
    """
    Provides various interactive language learning exercises.
    """
    topic_str = topic or "general vocabulary"

    if mode == "flashcards":
        return (
            f"🃏 **Flashcard Challenge: {target_language.title()}**\n\n"
            f"**Topic:** {topic_str.title()}\n"
            f"**Task:** Generate 5 flashcards for {target_language.title()} on the topic of {topic_str}. "
            f"For each card, provide the English word/phrase and its {target_language.title()} equivalent."
        )

    elif mode == "quiz":
        return (
            f"🧠 **Quiz Time! {target_language.title()}**\n\n"
            f"**Topic:** {topic_str.title()}\n"
            f"**Task:** Create a short, multiple-choice quiz for {target_language.title()} on the topic of {topic_str}. "
            f"Ask at least 3 questions with 3 options each."
        )

    elif mode == "roleplay":
        return (
            f"🎭 **Roleplay Conversation: {target_language.title()}**\n\n"
            f"**Scenario:** You are a waiter in a restaurant. I am a customer.\n"
            f"**Task:** Start a conversation with me in {target_language.title()} as the waiter. "
            f"You will need to ask me what I would like to order."
        )

    elif mode == "fun_practice":
        return (
            f"🎮 **Fun Practice: {target_language.title()}**\n\n"
            f"**Topic:** {topic_str.title()}\n"
            f"**Task:** Create a fun, creative practice exercise for {target_language.title()}. "
            f"For example, you could ask me to describe a picture, or complete a story using new vocabulary."
        )

    else:
        return (
            f"❌ **Error:** Invalid mode '{mode}'. "
            f"Please choose from 'flashcards', 'quiz', 'roleplay', or 'fun_practice'."
        )


# --- Tool: image_analyzer (analyze image content) ---
IMAGE_ANALYZER_DESCRIPTION = RichToolDescription(
    description="Analyze image properties and content: dimensions, format, colors, basic image information.",
    use_when="Use this tool to get detailed information about an image without modifying it.",
    side_effects="Returns detailed analysis of the image properties and characteristics.",
)


@mcp.tool(description=IMAGE_ANALYZER_DESCRIPTION.model_dump_json())
async def image_analyzer(
    puch_image_data: Annotated[
        str, Field(description="Base64-encoded image data to analyze")
    ],
) -> str:
    """
    Analyze image properties and provide detailed information.
    """
    import base64
    import io
    from PIL import Image
    from collections import Counter

    try:
        # Decode image
        image_bytes = base64.b64decode(puch_image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Basic properties
        width, height = image.size
        mode = image.mode
        format_name = image.format or "Unknown"

        # File size
        file_size_kb = len(image_bytes) / 1024

        # Color analysis (for RGB images)
        color_info = ""
        if mode in ["RGB", "RGBA"]:
            # Sample colors from the image
            sample_image = image.resize((50, 50))  # Downsample for performance
            colors = list(sample_image.getdata())

            if mode == "RGBA":
                # Remove alpha channel for color analysis
                colors = [(r, g, b) for r, g, b, a in colors]

            # Find dominant colors
            color_counts = Counter(colors)
            dominant_colors = color_counts.most_common(5)

            color_info = "\n**Dominant Colors:**\n"
            for i, (color, count) in enumerate(dominant_colors, 1):
                r, g, b = color
                color_info += f"{i}. RGB({r}, {g}, {b}) - {count} pixels\n"

        # Aspect ratio
        aspect_ratio = round(width / height, 2)

        # Image analysis result
        analysis = (
            f"🔍 **Image Analysis Report**\n\n"
            f"**Basic Properties:**\n"
            f"• Dimensions: {width} × {height} pixels\n"
            f"• Aspect Ratio: {aspect_ratio}:1\n"
            f"• Color Mode: {mode}\n"
            f"• Format: {format_name}\n"
            f"• File Size: {file_size_kb:.1f} KB\n"
            f"{color_info}\n"
            f"**Image Classification:**\n"
            f"• Resolution: {'High' if width * height > 1000000 else 'Medium' if width * height > 300000 else 'Low'}\n"
            f"• Orientation: {'Landscape' if width > height else 'Portrait' if height > width else 'Square'}\n\n"
            f"**Recommendations:**\n"
            f"• Suitable for: {'Print and web' if width >= 1920 else 'Web only' if width >= 800 else 'Thumbnails'}\n"
            f"• Quality: {'Excellent' if file_size_kb > 500 else 'Good' if file_size_kb > 100 else 'Compressed'}"
        )

        return analysis

    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Image analysis failed: {str(e)}")
        )


# --- Run MCP Server ---
async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)


if __name__ == "__main__":
    asyncio.run(main())
