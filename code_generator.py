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


DESIGN_KIT_SYSTEM = """You are an elite design-systems engineer. You are given screenshots of every screen of a web app plus a design spec (with animation timings) extracted from a demo video of it.

Your job: write DESIGN.md — a style guide that lets an AI coding agent build a BRAND-NEW app that is visually and kinetically indistinguishable from this one. The agent will never see the video; your document and these screenshots are all it gets. It must be prescriptive instructions, not documentation.

Ground every value in the screenshots. Where the written spec and the screenshots disagree, trust the screenshots. Estimate exact hex values, px sizes, and weights by looking at the pixels.

Structure DESIGN.md as:

1. **Identity** — one tight paragraph on the feel (density, contrast, warmth, energy) an agent should aim for.
2. **Tokens** — a table of exact values: every color (hex) with its usage rule, font family/sizes/weights, spacing scale, radii per element type, shadow definitions. Phrase usage as rules: "Surfaces are #17181C with a 1px #26282D border — never elevate with shadows alone."
3. **Typography & spacing rhythm** — the hierarchy and the base grid, with rules for when each step applies.
4. **Components** — for each recurring component (buttons, cards, nav, inputs, tables, modals...): exact styling rules for every state (default/hover/focus/active/selected/disabled), followed by a canonical, copy-paste-ready TSX + Tailwind snippet. The agent should copy these patterns, not re-derive them.
5. **Motion** — the most important section. A table of every animation: element | trigger | effect | duration (ms) | easing (exact CSS value). Then generalize into motion RULES the agent can apply to components that never appeared in the demo ("all hover transitions: 150ms ease-out on background/border only", "overlays enter: scale 0.98→1 + fade, 200ms cubic-bezier(...)"). Include the @keyframes / transition CSS snippets ready to paste.
6. **States & interaction details** — focus rings, selection styles, loading/skeleton patterns, scroll behaviors (sticky headers, reveal-on-scroll).
7. **Do / Don't** — 6-10 sharp rules that prevent the agent from drifting off-style (fonts it must never use, effects that would break the identity, etc.).

Every rule must be specific enough that two different agents following it produce the same pixels. No vague words like "modern" or "clean" without the concrete values that define them.

Return ONLY the markdown content of DESIGN.md. No fences around the whole document, no commentary."""

CLAUDE_MD_SNIPPET = """# How to use this design kit

This kit is a **style pack for AI coding agents** (Claude Code, etc.). It captures another app's
look, feel, and animations so YOUR app comes out in that visual language — you never have to
describe the style in a prompt.

What's inside:

- `DESIGN.md` — the style guide (tokens, component patterns, motion rules). This is what the agent reads.
- `tokens.css` — the color/font/radius/shadow theme as a ready-to-use Tailwind v4 stylesheet.
- `refs/` — reference screenshots of the original app, for visual grounding.

---

## Setup (both cases)

1. Copy the `design-kit/` folder into the ROOT of your project.
2. Add the block below to your project's `CLAUDE.md` (create the file if it doesn't exist,
   append if it does):

```markdown
## Design system

All UI in this project MUST follow `design-kit/DESIGN.md` exactly — tokens, component patterns, and the motion rules.

- Import `design-kit/tokens.css` as the Tailwind theme (copy it into `app/globals.css`). Never invent new colors, radii, shadows, fonts, or animation durations — every value comes from the tokens or DESIGN.md.
- Before building any screen or component, look at the screenshots in `design-kit/refs/` and match their density, contrast, and proportions.
- Copy the component snippets in DESIGN.md as starting points instead of writing components from scratch.
- Every interactive element gets the motion treatment from DESIGN.md's Motion section — exact durations and easings, no defaults.
- If DESIGN.md doesn't cover a case, extrapolate from its rules and the reference screenshots — never fall back to generic styling.
```

That's it. Claude Code reads CLAUDE.md automatically every session.

---

## Case 1: Building a NEW app

Just build. Open Claude Code in the project and describe what you want — never mention the style:

> "Set up a Next.js app and build a landing page for my workout tracker: hero, features section, signup form."

Every screen you ask for comes out in the kit's style automatically. For a screen that should
mirror a specific original screen, point at a reference:

> "Build the settings page. Match the feel and density of design-kit/refs/02-settings.png."

---

## Case 2: Restyling an EXISTING app

Work in layers, on a branch (`git checkout -b restyle`) — one giant restyle is unreviewable.
Check the result in your dev server after each layer:

**Layer 1 — theme.** Gets you ~70% of the look with zero markup changes:

> "Restyle this app to match design-kit/DESIGN.md. Start with the theme layer only: replace our colors, fonts, radii, and shadows with design-kit/tokens.css — merge it into our globals/tailwind config and map our existing CSS variables to the new tokens. Don't touch component markup yet."

**Layer 2 — motion:**

> "Now the motion pass: apply the Motion rules from DESIGN.md across the app — hover transitions, entry animations, the duration/easing table. Replace our existing transitions."

**Layer 3 — components, one screen at a time:**

> "Restyle the dashboard page to match the component patterns in DESIGN.md — buttons, cards, and nav follow its snippets. Compare against design-kit/refs/ for density and spacing."

Your app does NOT need to be Next.js or Tailwind — DESIGN.md is just colors, type, and motion
rules; the agent translates them into whatever your codebase uses. `tokens.css` is a convenience
for Tailwind projects; on other stacks, ask the agent to port the values into your styling system.
"""


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", (name or "").lower()).strip("-") or "screen"


def generate_design_kit(app_spec: dict, frames: dict | None = None) -> dict:
    """
    Generate a portable design kit: DESIGN.md (AI-facing style guide),
    tokens.css (Tailwind theme), and the reference screenshots.
    Claude writes the guide while looking at ALL keyframes so every
    value is grounded in actual pixels.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    frames = frames or {}
    screens = app_spec.get("screens", [])

    files: dict = {}
    content: list[dict] = []
    for i, screen in enumerate(screens[:20]):
        name = screen.get("name", f"screen-{i}")
        frame_path = frames.get(name)
        if not frame_path:
            continue
        ref_name = f"refs/{i:02d}-{_slugify(name)}.png"
        with open(frame_path, "rb") as f:
            files[ref_name] = f.read()
        content.append(_encode_image(frame_path))
        content.append({
            "type": "text",
            "text": f"Above: screenshot of the \"{name}\" screen (saved in the kit as {ref_name}).",
        })

    content.append({
        "type": "text",
        "text": (
            "## Full design spec extracted from the demo video\n"
            + json.dumps(app_spec, indent=2)
            + "\n\nWrite DESIGN.md now. Ground every value in the screenshots above; "
            "trust them over the spec where they disagree. Reference the screenshots "
            "by their refs/ filenames where a visual example helps."
        ),
    })

    print("Writing DESIGN.md with Claude (grounded on all keyframes)...")
    files["DESIGN.md"] = _strip_fences(_claude_call(client, DESIGN_KIT_SYSTEM, content))

    print("Generating tokens.css with Claude...")
    foundation_context = {
        "appName": app_spec.get("appName"),
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
    files["tokens.css"] = foundation_files.get(
        "app/globals.css", "/* foundation generation failed — see DESIGN.md tokens */"
    )

    files["README.md"] = CLAUDE_MD_SNIPPET
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
