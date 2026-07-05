"""
Code Generator — turns a design spec (+ keyframe screenshots) into a
Next.js + TypeScript + Tailwind project that replicates the demoed UI,
animations included.
"""

from __future__ import annotations

import base64
import json
import re
from google import genai as google_genai
import anthropic

import config

gemini_client = google_genai.Client(api_key=config.GEMINI_API_KEY)

FOUNDATION_SYSTEM = """You are an elite frontend engineer setting up the design foundation of a Next.js 15 (App Router) + TypeScript + Tailwind CSS v4 project.

You are given design tokens, typography, and navigation info extracted from a demo video of a web app. Produce exactly two files:

1. `app/globals.css` — starts with `@import "tailwindcss";`, then an `@theme` block mapping the design tokens to Tailwind theme variables (colors, radii, shadows, fonts), then `:root` CSS variables for anything pages need directly, then any shared `@keyframes` implied by the spec's animations/transitions.
2. `app/layout.tsx` — the root layout: imports `./globals.css`, loads the closest matching Google font via `next/font/google`, sets metadata (title from the app name), and applies base body classes (background, text color, font).

Return a JSON object mapping the two file paths to their full contents:
{"app/globals.css": "...", "app/layout.tsx": "..."}

Return ONLY the JSON object — no markdown fences, no commentary."""

PAGE_GEN_SYSTEM = """You are an elite frontend engineer who specializes in pixel-perfect UI replication.

You are given:
1. A screenshot of one screen of a web app (the ground truth for how it must look)
2. Global design tokens and the `app/globals.css` theme already set up for this project
3. A detailed spec for this screen, including animations with durations and easing
4. A map of the app's routes so you can wire up navigation

Produce a single, complete Next.js App Router page component (TypeScript, Tailwind CSS v4) that replicates this screen EXACTLY:

- Start the file with `"use client";` so interactions and animations work.
- Match the screenshot pixel-for-pixel: layout proportions, colors, typography, spacing, shadows, radii. When the screenshot and the written spec disagree, trust the screenshot.
- Reproduce the text content visible in the screenshot verbatim.
- Style with Tailwind utility classes, referencing the theme variables from globals.css (e.g. `bg-surface`, `text-muted`, or arbitrary values like `bg-[var(--color-surface)]`) — do not invent a second design system.
- Implement EVERY animation in the spec with its stated duration and easing: Tailwind transition utilities with arbitrary values (e.g. `duration-[300ms] ease-[cubic-bezier(0.34,1.56,0.64,1)]`), and React state for click/toggle triggers. Define page-specific `@keyframes` in a `<style>` element inside the component if they aren't in globals.css. Include hover/focus/active states and entry (page-load) animations so the page feels alive like the original.
- Define any subcomponents in this same file — the file must be self-contained apart from `next/link`, `next/image` (avoid remote images; use divs/gradients/SVG for imagery), React, and globals.css.
- Navigation elements must use `<Link href="...">` with the routes from the provided route map.
- Use semantic HTML and make the layout degrade gracefully when resized.

Return ONLY the raw TSX file content. No markdown fences, no commentary before or after."""


def _route_to_page(route: str, index: int) -> tuple[str, str]:
    """Map a spec route to (next_route, page_file). First screen is always /."""
    slug = re.sub(r"[^a-z0-9/-]", "-", (route or "").strip("/").lower()).strip("-/")
    if index == 0 or not slug:
        if index == 0:
            return "/", "app/page.tsx"
        slug = f"page-{index}"
    return f"/{slug}", f"app/{slug}/page.tsx"


def _encode_image(path: str) -> dict:
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": data},
    }


def _strip_fences(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _claude_call(client: anthropic.Anthropic, system: str, content: list | str) -> str:
    """One streaming Claude call, returns the concatenated text output."""
    with client.messages.stream(
        model=config.ANTHROPIC_CODE_MODEL,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        response = stream.get_final_message()
    return "".join(b.text for b in response.content if b.type == "text")


def _scaffold(app_name: str) -> dict:
    """Static Next.js + TypeScript + Tailwind v4 boilerplate."""
    slug = re.sub(r"[^a-z0-9-]", "-", (app_name or "replicated-ui").lower()).strip("-") or "replicated-ui"
    return {
        "package.json": json.dumps({
            "name": slug,
            "private": True,
            "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
            "dependencies": {
                "next": "^15.3.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
            },
            "devDependencies": {
                "typescript": "^5",
                "@types/node": "^20",
                "@types/react": "^19",
                "@types/react-dom": "^19",
                "tailwindcss": "^4",
                "@tailwindcss/postcss": "^4",
            },
        }, indent=2),
        "tsconfig.json": json.dumps({
            "compilerOptions": {
                "target": "ES2017",
                "lib": ["dom", "dom.iterable", "esnext"],
                "allowJs": True,
                "skipLibCheck": True,
                "strict": True,
                "noEmit": True,
                "esModuleInterop": True,
                "module": "esnext",
                "moduleResolution": "bundler",
                "resolveJsonModule": True,
                "isolatedModules": True,
                "jsx": "preserve",
                "incremental": True,
                "plugins": [{"name": "next"}],
                "paths": {"@/*": ["./*"]},
            },
            "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
            "exclude": ["node_modules"],
        }, indent=2),
        "next.config.ts": (
            "import type { NextConfig } from \"next\";\n\n"
            "const nextConfig: NextConfig = {};\n\n"
            "export default nextConfig;\n"
        ),
        "postcss.config.mjs": (
            "const config = {\n"
            "  plugins: {\n"
            "    \"@tailwindcss/postcss\": {},\n"
            "  },\n"
            "};\n\n"
            "export default config;\n"
        ),
        ".gitignore": "node_modules/\n.next/\nout/\n*.tsbuildinfo\nnext-env.d.ts\n",
    }


def generate_with_anthropic(app_spec: dict, frames: dict | None = None) -> dict:
    """Generate a Next.js project with Claude, one page per screen, grounded on screenshots."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    frames = frames or {}

    screens = app_spec.get("screens", [])
    if not screens:
        return {"error.txt": "Spec contained no screens to generate."}

    route_map = {
        s.get("name", f"screen-{i}"): _route_to_page(s.get("route", ""), i)
        for i, s in enumerate(screens)
    }
    pages_for_prompt = {name: route for name, (route, _) in route_map.items()}

    app_name = app_spec.get("appName", "Replicated UI")
    files = _scaffold(app_name)

    # Foundation: globals.css theme + root layout from the design tokens
    print("Generating design foundation (globals.css + layout.tsx) with Claude...")
    foundation_context = {
        "appName": app_name,
        "designTokens": app_spec.get("designTokens"),
        "navigation": app_spec.get("navigation"),
        "screenTransitions": app_spec.get("screenTransitions"),
        "animationsAcrossScreens": [
            a for s in screens for a in s.get("animations", [])
        ],
    }
    foundation_raw = _claude_call(
        client, FOUNDATION_SYSTEM, json.dumps(foundation_context, indent=2)
    )
    foundation_files = _parse_files_response(foundation_raw)
    if "app/globals.css" not in foundation_files:
        return {"error.txt": f"Foundation generation failed:\n\n{foundation_raw}"}
    files.update(foundation_files)

    shared_context = {
        "appName": app_name,
        "designTokens": app_spec.get("designTokens"),
        "navigation": app_spec.get("navigation"),
        "routes": pages_for_prompt,
    }

    for i, screen in enumerate(screens):
        name = screen.get("name", f"screen-{i}")
        route, page_file = route_map[name]
        print(f"Generating {page_file} ({name}) with Claude...")

        content: list[dict] = []
        frame_path = frames.get(name)
        if frame_path:
            content.append(_encode_image(frame_path))
            content.append({
                "type": "text",
                "text": "Above is the reference screenshot for this screen — replicate it exactly.",
            })
        content.append({
            "type": "text",
            "text": (
                "## Global design context\n"
                + json.dumps(shared_context, indent=2)
                + "\n\n## app/globals.css (already in the project — use its theme)\n"
                + files["app/globals.css"]
                + "\n\n## Spec for THIS screen (generate this page)\n"
                + json.dumps(screen, indent=2)
                + f"\n\nThis page is served at route `{route}` ({page_file}). "
                "Link navigation items to the other routes listed in `routes` using next/link."
            ),
        })

        tsx = _claude_call(client, PAGE_GEN_SYSTEM, content)
        files[page_file] = _strip_fences(tsx)

    files["README.md"] = (
        f"# {app_name}\n\n"
        f"{app_spec.get('description', '')}\n\n"
        "Next.js + TypeScript + Tailwind CSS replica generated from a screen recording.\n\n"
        "```bash\nnpm install\nnpm run dev\n```\n\n"
        "Open http://localhost:3000\n\n"
        "## Pages\n"
        + "\n".join(f"- `{route}` — {name}" for name, (route, _) in route_map.items())
        + "\n"
    )
    return files


LEGACY_GEMINI_PROMPT = """You are an expert frontend developer. You are given a design specification (JSON) extracted from a screen recording of a web app.

Generate a complete Next.js 15 (App Router) + TypeScript + Tailwind CSS project that replicates the UI, one route per screen, including every animation with its stated duration and easing. Include all config files (package.json, tsconfig.json, postcss config, app/globals.css, app/layout.tsx).

Return a JSON object where each key is a file path and each value is the file content. Return ONLY the JSON object, no markdown, no explanation.

## Design Specification:
"""


def generate_with_gemini(app_spec: dict) -> dict:
    """Generate project files using Gemini (text-only fallback, no screenshots)."""
    prompt = LEGACY_GEMINI_PROMPT + json.dumps(app_spec, indent=2)

    response = gemini_client.models.generate_content(
        model=config.GEMINI_CODE_MODEL,
        contents=[prompt],
    )

    return _parse_files_response(response.text)


def generate_project(app_spec: dict, frames: dict | None = None) -> dict:
    """Generate project files using the configured provider."""
    provider = config.CODE_GEN_PROVIDER.lower()

    print(f"Generating code with {provider}...")

    if provider == "gemini":
        return generate_with_gemini(app_spec)
    return generate_with_anthropic(app_spec, frames)


def _parse_files_response(raw_text: str) -> dict:
    """Parse an LLM JSON response into a dict of filepath -> content."""
    raw_text = _strip_fences(raw_text)

    try:
        files = json.loads(raw_text)
        if isinstance(files, dict):
            return files
    except json.JSONDecodeError:
        pass

    return {"error.txt": f"Could not parse code generation response:\n\n{raw_text}"}
