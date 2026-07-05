import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_projects")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gemini model for video understanding
GEMINI_VIDEO_MODEL = "gemini-2.5-flash"

# Model for code generation (can be "gemini" or "anthropic")
CODE_GEN_PROVIDER = os.getenv("CODE_GEN_PROVIDER", "gemini")
GEMINI_CODE_MODEL = "gemini-2.5-flash"
ANTHROPIC_CODE_MODEL = "claude-sonnet-4-20250514"
