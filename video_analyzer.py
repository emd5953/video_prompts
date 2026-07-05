"""
Video Analyzer — uploads a screen recording to Gemini and extracts a
design-fidelity spec: exact layout, design tokens, component states,
and animation timing for every screen shown.
"""

import json
import time
from google import genai

import config

client = genai.Client(api_key=config.GEMINI_API_KEY)

ANALYSIS_PROMPT = """You are an expert UI reverse-engineer. You are watching a screen recording of someone demoing a web application's UI.

Your job is to extract a pixel-level DESIGN specification — not a feature spec. Another AI will use your spec plus screenshots to reproduce the EXACT visual appearance, interactions, and animations of this UI.

Watch closely for:
- Every distinct screen/page and WHEN it appears (timestamps)
- Exact layout structure: columns, sidebars, grids, spacing rhythm, alignment
- Design tokens: precise colors (estimate hex values), font families, font sizes/weights, border radii, shadows, spacing scale
- Component states: default, hover, focus, active, selected, disabled — anything the demo reveals
- ANIMATIONS AND TRANSITIONS: what moves, what triggers it, how long it takes (estimate in ms), and the easing feel (linear, ease-out, spring/bouncy, etc.)
- Screen-to-screen navigation transitions (fades, slides, instant swaps)
- Scroll behavior (sticky headers, parallax, reveal-on-scroll)
- The actual text content and data visible on screen (reproduce it verbatim where readable)

For each screen, pick a "timestamp" (in seconds from the start of the video) where the screen is fully rendered, static, and unobstructed — this frame will be extracted as a reference screenshot.

Return a JSON object with this structure:

{
  "appName": "string — inferred name of the app",
  "description": "string — one paragraph describing the UI being demoed",
  "designTokens": {
    "colors": {
      "background": "hex", "surface": "hex", "primary": "hex",
      "secondary": "hex", "text": "hex", "textMuted": "hex",
      "border": "hex", "accent": "hex"
    },
    "typography": {
      "fontFamily": "string — closest web-safe or Google font",
      "headingWeight": "string", "bodySize": "string — e.g. 14px",
      "scale": "string — describe the size hierarchy"
    },
    "spacing": "string — base unit and rhythm, e.g. 8px grid",
    "radii": "string — e.g. 8px cards, 6px buttons, full pills",
    "shadows": "string — CSS-like description of elevation styles"
  },
  "screens": [
    {
      "name": "string — screen name",
      "route": "string — suggested URL route, e.g. / or /settings",
      "timestamp": 12.5,
      "description": "string — what this screen shows",
      "layout": "string — precise layout structure (regions, widths, alignment)",
      "components": [
        {
          "type": "string — e.g. Navbar, Card, Table, Modal",
          "description": "string — content and exact placement",
          "styling": "string — colors, sizes, spacing, borders specific to this component",
          "states": "string — hover/focus/active/selected appearances seen in the demo"
        }
      ],
      "animations": [
        {
          "element": "string — what animates",
          "trigger": "string — page load | hover | click | scroll | etc.",
          "description": "string — what visually happens",
          "durationMs": 300,
          "easing": "string — CSS easing, e.g. ease-out, cubic-bezier(0.34,1.56,0.64,1)"
        }
      ],
      "interactions": ["string — each user interaction demoed on this screen"],
      "visibleText": "string — headings, labels, and sample data readable on screen"
    }
  ],
  "screenTransitions": [
    {
      "from": "screen name", "to": "screen name",
      "trigger": "string — what the user did",
      "description": "string — how the transition looks",
      "durationMs": 250,
      "easing": "string"
    }
  ],
  "navigation": {
    "type": "string — sidebar | topnav | tabs | etc.",
    "items": ["string — nav item labels, verbatim"]
  }
}

Be obsessive about visual detail and animation timing — the goal is an exact replica, not a functional approximation.
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
    """Upload a video and get a design-fidelity spec from Gemini."""
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
