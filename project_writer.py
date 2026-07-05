"""
Project Writer — takes generated file dict and writes them to disk, then zips.
"""

import os
import shutil
import json

import config


def write_project(project_name: str, files: dict) -> str:
    """Write generated files to disk and return the project directory path."""
    # Sanitize project name
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in project_name)
    project_dir = os.path.join(config.OUTPUT_DIR, safe_name)

    # Clean up if exists
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)

    os.makedirs(project_dir, exist_ok=True)

    for filepath, content in files.items():
        full_path = os.path.join(project_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            if isinstance(content, dict):
                f.write(json.dumps(content, indent=2))
            else:
                f.write(str(content))

    print(f"Project written to: {project_dir}")
    return project_dir


def zip_project(project_dir: str) -> str:
    """Zip a project directory and return the zip file path."""
    zip_path = shutil.make_archive(project_dir, "zip", project_dir)
    print(f"Project zipped: {zip_path}")
    return zip_path
