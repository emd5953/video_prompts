# Video to App

Screen-record a demo of any web app's UI. Get back a pixel-faithful Next.js + TypeScript + Tailwind CSS replica — animations included.

## How it works

1. You upload a screen recording of a web app being demoed
2. Gemini watches the video and extracts a design spec: layout, design tokens, component states, and animation timing (durations + easing), plus a timestamp for each screen
3. ffmpeg extracts a reference screenshot per screen at those timestamps
4. Claude maps the design tokens into a Tailwind v4 theme (`globals.css` + root layout), then gets each screen's spec **and** screenshot and generates one App Router page per screen, with the animations wired up
5. You download the project as a zip, then `npm install && npm run dev`

## Two output modes

- **Replica** — a runnable Next.js project that clones the demoed app screen-for-screen.
- **Design kit** (`--kit` in the CLI, "Generate Design Kit" in the UI) — a portable style-guide package for building *new* apps in the demoed app's visual language:
  - `DESIGN.md` — an AI-facing style guide: exact tokens, per-state component rules with copy-paste TSX/Tailwind snippets, and a motion table (every animation with duration + easing) generalized into rules
  - `tokens.css` — the Tailwind v4 theme, ready to drop into `app/globals.css`
  - `refs/` — the keyframe screenshots, for visual grounding
  - `README.md` — a ready-to-paste CLAUDE.md snippet that makes Claude Code follow the kit in your new project

## Setup

```bash
pip install -r requirements.txt
brew install ffmpeg   # needed for keyframe extraction
cp .env.example .env
# Add GEMINI_API_KEY and ANTHROPIC_API_KEY to .env
```

## Usage

### Web UI

```bash
python -m uvicorn server:app --reload --port 8000
```

Open http://localhost:8000

### CLI

```bash
python pipeline.py path/to/demo-video.mp4
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI API key (video analysis) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key (UI generation) |
| `CODE_GEN_PROVIDER` | No | `anthropic` (default, screenshot-grounded) or `gemini` (text-only fallback) |
