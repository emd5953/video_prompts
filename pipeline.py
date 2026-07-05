"""
Pipeline — orchestrates the full video-to-app flow.
Can be used as CLI or imported by the server.
"""

from __future__ import annotations

import json
import os

from video_analyzer import analyze_video
from frame_extractor import extract_frames
from code_generator import generate_project
from project_writer import write_project, zip_project


def run_pipeline(video_path: str, spec_override: dict | None = None) -> dict:
    """
    Full pipeline: video → analysis → code generation → project files.
    If spec_override is provided, skips video analysis and uses that spec directly.
    """
    result = {
        "status": "started",
        "video_path": video_path,
    }

    # Step 1: Analyze the video (or use provided spec)
    if spec_override:
        print("\n=== Using provided spec (skipping video analysis) ===")
        app_spec = spec_override
    else:
        print("\n=== Step 1: Analyzing video with Gemini ===")
        app_spec = analyze_video(video_path)

    result["app_spec"] = app_spec

    app_name = app_spec.get("appName", "generated-app")
    print(f"Detected app: {app_name}")
    print(f"Description: {app_spec.get('description', 'N/A')}")
    print(f"Screens found: {len(app_spec.get('screens', []))}")

    # Save the spec for reference
    spec_path = os.path.join(os.path.dirname(video_path), f"{app_name}-spec.json")
    with open(spec_path, "w") as f:
        json.dump(app_spec, f, indent=2)
    result["spec_path"] = spec_path
    print(f"Spec saved to: {spec_path}")

    # Step 2: Extract reference screenshots at the spec's timestamps
    print("\n=== Step 2: Extracting keyframes ===")
    frames = extract_frames(video_path, app_spec) if os.path.exists(video_path) else {}
    result["frames_count"] = len(frames)

    # Step 3: Generate code
    print("\n=== Step 3: Generating project code ===")
    files = generate_project(app_spec, frames)
    result["files_count"] = len(files)
    print(f"Generated {len(files)} files")

    # Step 4: Write project to disk
    print("\n=== Step 4: Writing project files ===")
    project_dir = write_project(app_name, files)
    result["project_dir"] = project_dir

    # Step 5: Zip it up
    zip_path = zip_project(project_dir)
    result["zip_path"] = zip_path

    result["status"] = "complete"
    print(f"\n=== Done! Project ready at: {project_dir} ===")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <video_path>")
        print("       python pipeline.py <video_path> --spec <spec.json>")
        sys.exit(1)

    video_path = sys.argv[1]
    spec = None

    if "--spec" in sys.argv:
        spec_idx = sys.argv.index("--spec") + 1
        with open(sys.argv[spec_idx]) as f:
            spec = json.load(f)

    run_pipeline(video_path, spec_override=spec)
