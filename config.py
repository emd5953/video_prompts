import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_projects")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gemini model for video understanding (motion, timing, animation analysis)
GEMINI_VIDEO_MODEL = "gemini-2.5-flash"

# Model for code generation (can be "anthropic" or "gemini")
# Anthropic is the default: Claude gets the extracted keyframe screenshots
# alongside the design spec, which produces far more faithful UI.
CODE_GEN_PROVIDER = os.getenv("CODE_GEN_PROVIDER", "anthropic")
GEMINI_CODE_MODEL = "gemini-2.5-flash"
ANTHROPIC_CODE_MODEL = "claude-opus-4-8"
