"""
Video Analyzer — uploads a video to Gemini and extracts a structured app spec.
"""

import json
import time
from google import genai

import config

client = genai.Client(api_key=config.GEMINI_API_KEY)

ANALYSIS_PROMPT = """You are an expert app reverse-engineer. You are watching a video demo of an application.

Your job is to analyze every detail of this app and produce a comprehensive, structured specification that another AI can use to rebuild it from scratch.

Pay close attention to:
- Every screen/page shown
- All UI components (buttons, inputs, cards, modals, sidebars, navbars, tables, etc.)
- Layout and positioning (grid, flex, sidebar + main, etc.)
- Colors, fonts, spacing, border radius, shadows — the visual design system
- Navigation flow (how screens connect, what triggers transitions)
- User interactions (clicks, hovers, drags, form submissions)
- Data being displayed (what kind of content, structure, sample data)
- Any animations or transitions
- Responsive behavior if shown

Return a JSON object with this structure:

{
  "appName": "string — inferred name of the app",
  "description": "string — one paragraph describing what the app does",
  "techStack": {
    "recommendation": "string — recommended tech stack (e.g., Next.js + Tailwind)",
    "reasoning": "string — why this stack fits"
  },
  "designSystem": {
    "colorScheme": "light | dark | both",
    "primaryColor": "string — hex",
    "secondaryColor": "string — hex",
    "backgroundColor": "string — hex",
    "textColor": "string — hex",
    "fontFamily": "string",
    "borderRadius": "string — e.g., 8px, rounded-lg",
    "spacing": "string — general spacing approach",
    "shadows": "string — shadow style if any"
  },
  "screens": [
    {
      "name": "string — screen name",
      "route": "string — suggested URL route",
      "description": "string — what this screen does",
      "layout": "string — describe the layout structure",
      "components": [
        {
          "type": "string — component type (e.g., Navbar, Card, Table, Form, Modal)",
          "description": "string — detailed description of the component",
          "props": "object — key properties, content, and behavior",
          "styling": "string — specific styling notes"
        }
      ],
      "interactions": ["string — describe each user interaction on this screen"]
    }
  ],
  "dataModels": [
    {
      "name": "string — model name",
      "fields": [
        {
          "name": "string",
          "type": "string",
          "description": "string"
        }
      ]
    }
  ],
  "navigation": {
    "type": "string — sidebar | topnav | tabs | bottom-nav | etc.",
    "items": ["string — nav item names"]
  },
  "sampleData": "object — representative sample data to populate the app"
}

Be extremely thorough. The more detail you provide, the better the generated app will match the original.
Return ONLY the JSON object, no markdown fences, no explanation."""


def upload_video(video_path: str) -> object:
    """Upload a video file to Gemini's File API and wait for processing."""
    print(f"Uploading video: {video_path}")
    uploaded_file = client.files.upload(file=video_path)
    print(f"Upload complete. File name: {uploaded_file.name}, state: {uploaded_file.state}")

    # Wait for the video to be processed
    while uploaded_file.state.name == "PROCESSING":
        print("Video is processing... waiting 5 seconds")
        time.sleep(5)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise RuntimeError(f"Video processing failed: {uploaded_file.state}")

    print(f"Video ready. State: {uploaded_file.state}")
    return uploaded_file


def analyze_video(video_path: str) -> dict:
    """Upload a video and get a structured app specification from Gemini."""
    uploaded_file = upload_video(video_path)

    print("Analyzing video with Gemini...")
    response = client.models.generate_content(
        model=config.GEMINI_VIDEO_MODEL,
        contents=[uploaded_file, ANALYSIS_PROMPT],
    )

    raw_text = response.text.strip()

    # Strip markdown fences if the model wraps them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("```", 1)[0]
    raw_text = raw_text.strip()

    try:
        app_spec = json.loads(raw_text)
    except json.JSONDecodeError:
        print("Warning: Could not parse JSON from Gemini response. Returning raw text.")
        app_spec = {"raw_response": raw_text}

    return app_spec
