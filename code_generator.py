"""
Code Generator — takes an app spec and generates a full project.
"""

import json
from google import genai as google_genai
import anthropic

import config

gemini_client = google_genai.Client(api_key=config.GEMINI_API_KEY)

CODE_GEN_PROMPT = """You are an expert full-stack developer. You are given a detailed app specification (JSON) that was extracted from a video demo of an application.

Your job is to generate a COMPLETE, working project that recreates this app as faithfully as possible.

## Rules:
1. Use the tech stack recommended in the spec, or default to Next.js + Tailwind CSS + TypeScript
2. Match the design system exactly — colors, fonts, spacing, border radius, shadows
3. Implement every screen described in the spec
4. Include all components with their described styling and behavior
5. Add the navigation structure as described
6. Populate the app with the sample data from the spec
7. Make it responsive
8. Include all necessary configuration files (package.json, tsconfig, tailwind config, etc.)

## Output Format:
Return a JSON object where each key is a file path and each value is the file content:

{
  "package.json": "{ ... }",
  "tsconfig.json": "{ ... }",
  "tailwind.config.ts": "...",
  "src/app/layout.tsx": "...",
  "src/app/page.tsx": "...",
  "src/app/globals.css": "...",
  "src/components/Navbar.tsx": "...",
  ...
}

Include EVERY file needed to run the project. The user should be able to run `npm install && npm run dev` and see the app.

Do NOT include explanations, markdown, or anything outside the JSON object.
Return ONLY the JSON object.

## App Specification:
"""


def generate_with_gemini(app_spec: dict) -> dict:
    """Generate project files using Gemini."""
    prompt = CODE_GEN_PROMPT + json.dumps(app_spec, indent=2)

    response = gemini_client.models.generate_content(
        model=config.GEMINI_CODE_MODEL,
        contents=[prompt],
    )

    return _parse_files_response(response.text)


def generate_with_anthropic(app_spec: dict) -> dict:
    """Generate project files using Claude."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = CODE_GEN_PROMPT + json.dumps(app_spec, indent=2)

    response = client.messages.create(
        model=config.ANTHROPIC_CODE_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_files_response(response.content[0].text)


def generate_project(app_spec: dict) -> dict:
    """Generate project files using the configured provider."""
    provider = config.CODE_GEN_PROVIDER.lower()

    print(f"Generating code with {provider}...")

    if provider == "anthropic":
        return generate_with_anthropic(app_spec)
    else:
        return generate_with_gemini(app_spec)


def _parse_files_response(raw_text: str) -> dict:
    """Parse the LLM response into a dict of filepath -> content."""
    raw_text = raw_text.strip()

    # Strip markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("```", 1)[0]
    raw_text = raw_text.strip()

    try:
        files = json.loads(raw_text)
        if isinstance(files, dict):
            return files
    except json.JSONDecodeError:
        pass

    return {"error.txt": f"Could not parse code generation response:\n\n{raw_text}"}
