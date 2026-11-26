"""Install the portable skill for supported local agents."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=("codex", "opencode", "claude", "all"), default="all")
    parser.add_argument("--force", action="store_true", help="Replace an existing installation")
    args = parser.parse_args()
    home = Path.home()
    targets = {
        "codex": home / ".codex" / "skills" / "youtube-context",
        "opencode": home / ".config" / "opencode" / "skills" / "youtube-context",
        "claude": home / ".claude" / "skills" / "youtube-context",
    }
    selected = targets if args.agent == "all" else {args.agent: targets[args.agent]}
    existing = [path for path in selected.values() if path.exists()]
    if existing and not args.force:
        parser.error("Already installed: " + ", ".join(map(str, existing)) + ". Use --force to update.")
    source = Path(__file__).resolve().parent / "skills" / "youtube-context"
    for agent, path in selected.items():
        path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, path, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"{agent}: {path}")
    print("Python and pip are required. yt-dlp will be installed automatically on first use if missing.")
    print("Restart the agent to load the skill.")


if __name__ == "__main__":
    main()
