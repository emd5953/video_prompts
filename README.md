# Video to App

Upload a video demo of any app. Get a working project back.

## How it works

1. You upload a video demo of an application
2. Gemini watches the video and extracts a detailed app specification
3. An LLM generates a complete project from that spec
4. You download the project as a zip and run it

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your GEMINI_API_KEY to .env
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
| `GEMINI_API_KEY` | Yes | Google AI API key |
| `ANTHROPIC_API_KEY` | No | Only if using Claude for code generation |
| `CODE_GEN_PROVIDER` | No | `gemini` (default) or `anthropic` |
