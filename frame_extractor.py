"""
Frame Extractor — pulls a reference screenshot per screen out of the video
at the timestamps Gemini identified, using ffmpeg.
"""

from __future__ import annotations

import os
import subprocess

import config


def extract_frames(video_path: str, app_spec: dict) -> dict:
    """
    Extract one keyframe per screen at its spec timestamp.
    Returns {screen_name: png_path} for every frame that was extracted.
    """
    stem = os.path.splitext(os.path.basename(video_path))[0]
    frames_dir = os.path.join(config.UPLOAD_DIR, f"{stem}_frames")
    os.makedirs(frames_dir, exist_ok=True)

    frames: dict[str, str] = {}
    for i, screen in enumerate(app_spec.get("screens", [])):
        name = screen.get("name", f"screen-{i}")
        timestamp = screen.get("timestamp")
        if not isinstance(timestamp, (int, float)) or timestamp < 0:
            print(f"Skipping frame for '{name}': no usable timestamp ({timestamp!r})")
            continue

        out_path = os.path.join(frames_dir, f"{i:02d}.png")
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                out_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            print(f"ffmpeg failed for '{name}' at {timestamp}s: {result.stderr[-300:]}")
            continue

        frames[name] = out_path
        print(f"Extracted frame for '{name}' at {timestamp}s -> {out_path}")

    return frames
