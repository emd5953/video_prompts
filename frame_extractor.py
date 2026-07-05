"""
Frame Extractor — pulls a reference screenshot per screen out of the video
at the timestamps Gemini identified, using ffmpeg.
"""

from __future__ import annotations

import os
import subprocess

import config


def _video_duration(video_path: str) -> float | None:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _normalize_timestamps(timestamps: list[float], duration: float | None) -> list[float]:
    """
    Models sometimes return timestamps as M.SS ("0.12" meaning 0:12) or as
    normalized 0-1 fractions instead of plain seconds. If every timestamp of a
    longer video sits under 1.0, seconds is implausible — detect which encoding
    was used and convert to real seconds.
    """
    if not timestamps or duration is None or duration <= 10:
        return timestamps
    nonzero = [t for t in timestamps if t > 0]
    if not nonzero or max(timestamps) >= 1.0:
        return timestamps

    # Fractional part ≥ .60 can't be M.SS seconds -> treat as normalized fraction
    if any(round((t % 1) * 100) >= 60 for t in nonzero):
        converted = [t * duration for t in timestamps]
        print(f"Timestamps looked normalized (0-1); rescaled by duration {duration:.1f}s")
    else:
        converted = [int(t) * 60 + round((t % 1) * 100) for t in timestamps]
        print("Timestamps looked like M.SS notation; converted to seconds")

    return [min(t, duration - 0.1) for t in converted]


def extract_frames(video_path: str, app_spec: dict) -> dict:
    """
    Extract one keyframe per screen at its spec timestamp.
    Returns {screen_name: png_path} for every frame that was extracted.
    """
    stem = os.path.splitext(os.path.basename(video_path))[0]
    frames_dir = os.path.join(config.UPLOAD_DIR, f"{stem}_frames")
    os.makedirs(frames_dir, exist_ok=True)

    screens = app_spec.get("screens", [])
    raw_ts = [
        s.get("timestamp") if isinstance(s.get("timestamp"), (int, float)) else -1.0
        for s in screens
    ]
    usable = [t for t in raw_ts if t >= 0]
    normalized = _normalize_timestamps(usable, _video_duration(video_path))
    ts_iter = iter(normalized)
    timestamps = [next(ts_iter) if t >= 0 else -1.0 for t in raw_ts]

    frames: dict[str, str] = {}
    for i, screen in enumerate(screens):
        name = screen.get("name", f"screen-{i}")
        timestamp = timestamps[i]
        if timestamp < 0:
            print(f"Skipping frame for '{name}': no usable timestamp ({screen.get('timestamp')!r})")
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
