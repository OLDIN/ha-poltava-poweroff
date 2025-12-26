#!/usr/bin/env python3
"""Script to bump version in manifest.json following semantic versioning."""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent.parent / "custom_components" / "poltava_poweroff" / "manifest.json"
REPO_ROOT = Path(__file__).parent.parent


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command and return result."""
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=check)


def get_current_version() -> str:
    """Get current version from manifest.json."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest.get("version", "0.0.0")


def get_latest_tag() -> str | None:
    """Get latest git tag."""
    result = run_command(["git", "describe", "--tags", "--abbrev=0"], check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def get_commits_since_tag(tag: str | None) -> list[str]:
    """Get commit messages since the last tag."""
    if tag:
        result = run_command(["git", "log", f"{tag}..HEAD", "--pretty=format:%s"])
    else:
        result = run_command(["git", "log", "--pretty=format:%s"])
    return [line for line in result.stdout.strip().split("\n") if line and not line.startswith("Bump version")]


def generate_changelog(commits: list[str], version: str) -> str:
    """Generate changelog from commit messages."""
    changelog = f"# Release {version}\n\n"
    changelog += f"Released: {datetime.now().strftime('%Y-%m-%d')}\n\n"

    if not commits:
        changelog += "No significant changes.\n"
        return changelog

    # Categorize commits
    features = []
    fixes = []
    docs = []
    other = []

    for commit in commits:
        lower = commit.lower()
        if any(word in lower for word in ["fix", "fixed", "bugfix", "bug"]):
            fixes.append(commit)
        elif any(word in lower for word in ["feat", "feature", "add", "added"]):
            features.append(commit)
        elif any(word in lower for word in ["doc", "docs", "documentation"]):
            docs.append(commit)
        else:
            other.append(commit)

    if features:
        changelog += "## ✨ Features\n\n"
        for commit in features:
            changelog += f"- {commit}\n"
        changelog += "\n"

    if fixes:
        changelog += "## 🐛 Bug Fixes\n\n"
        for commit in fixes:
            changelog += f"- {commit}\n"
        changelog += "\n"

    if docs:
        changelog += "## 📝 Documentation\n\n"
        for commit in docs:
            changelog += f"- {commit}\n"
        changelog += "\n"

    if other:
        changelog += "## 🔧 Other Changes\n\n"
        for commit in other:
            changelog += f"- {commit}\n"
        changelog += "\n"

    changelog += "## 🔄 Update Instructions\n\n"
    changelog += "1. Update via HACS or manually pull the latest version\n"
    changelog += "2. Restart Home Assistant\n"
    changelog += "3. Clear browser cache if needed\n"

    return changelog


def bump_version(current: str, part: str) -> str:
    """Bump version following semantic versioning."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", current)
    if not match:
        raise ValueError(f"Invalid version format: {current}. Expected format: X.Y.Z")

    major, minor, patch = map(int, match.groups())

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid version part: {part}. Use 'major', 'minor', or 'patch'")

    return f"{major}.{minor}.{patch}"


def update_manifest(version: str) -> None:
    """Update version in manifest.json."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["version"] = version

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"✅ Updated version in {MANIFEST_PATH.relative_to(REPO_ROOT)} to {version}")


def create_release_notes(version: str, changelog: str) -> Path:
    """Create release notes file."""
    notes_file = REPO_ROOT / f"RELEASE_NOTES_{version}.md"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(changelog)
    print(f"✅ Created release notes: {notes_file.relative_to(REPO_ROOT)}")
    return notes_file


def git_commit_and_tag(version: str, notes_file: Path | None = None, auto_push: bool = False) -> None:
    """Commit changes and create git tag."""
    # Add manifest.json
    run_command(["git", "add", str(MANIFEST_PATH)])

    # Add release notes if they exist
    if notes_file and notes_file.exists():
        run_command(["git", "add", str(notes_file)])

    # Commit
    commit_msg = f"Bump version to {version}"
    run_command(["git", "commit", "-m", commit_msg])
    print(f"✅ Committed: {commit_msg}")

    # Create tag
    tag = f"v{version}"
    tag_msg = f"Release {version}"
    run_command(["git", "tag", "-a", tag, "-m", tag_msg])
    print(f"✅ Created tag: {tag}")

    # Push if requested
    if auto_push:
        print("\n🚀 Pushing to GitHub...")
        run_command(["git", "push", "origin", "main"])
        print("✅ Pushed commits to origin/main")
        run_command(["git", "push", "origin", "--tags"])
        print("✅ Pushed tags to origin")


def main() -> None:
    """Main function."""
    auto_commit = "--commit" in sys.argv or "-c" in sys.argv
    auto_push = "--push" in sys.argv or "-p" in sys.argv
    generate_notes = "--notes" in sys.argv or "-n" in sys.argv

    # Remove flags from argv
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    if len(args) < 1:
        current = get_current_version()
        print(f"Current version: {current}")
        print("\n📖 Usage: python scripts/bump_version.py <major|minor|patch> [options]")
        print("\n📋 Options:")
        print("  -c, --commit    Automatically commit and tag")
        print("  -p, --push      Push commits and tags to GitHub (implies --commit)")
        print("  -n, --notes     Generate release notes from commits")
        print("\n💡 Examples:")
        print("  python scripts/bump_version.py patch           # 0.1.0 -> 0.1.1 (manual)")
        print("  python scripts/bump_version.py patch -c        # Update, commit & tag")
        print("  python scripts/bump_version.py minor -c -n     # Update, commit, tag & generate notes")
        print("  python scripts/bump_version.py patch -p -n     # Full release (commit, tag, push, notes)")
        sys.exit(1)

    part = args[0].lower()
    if part not in ("major", "minor", "patch"):
        print(f"❌ Error: Invalid version part '{part}'. Use 'major', 'minor', or 'patch'")
        sys.exit(1)

    # Get version info
    current = get_current_version()
    new_version = bump_version(current, part)
    latest_tag = get_latest_tag()

    print(f"📦 Version bump: {current} → {new_version}")
    print()

    # Update manifest
    update_manifest(new_version)

    # Generate release notes if requested
    notes_file = None
    if generate_notes or auto_push:
        commits = get_commits_since_tag(latest_tag)
        changelog = generate_changelog(commits, new_version)
        notes_file = create_release_notes(new_version, changelog)
        print()
        print("📝 Release notes preview:")
        print("─" * 60)
        print(changelog)
        print("─" * 60)
        print()

    # Commit and tag if requested
    if auto_commit or auto_push:
        print("🔨 Git operations:")
        try:
            git_commit_and_tag(new_version, notes_file=notes_file, auto_push=auto_push)
            print()
            print("✅ Release prepared successfully!")

            if not auto_push:
                print("\n💡 Next steps:")
                print("   1. Review changes: git log -1 --stat")
                print("   2. Push: git push origin main --tags")
                print(
                    f"   3. Create GitHub release: https://github.com/OLDIN/ha-poltava-poweroff/releases/new?tag=v{new_version}"
                )
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error during git operations: {e}")
            print(f"   stdout: {e.stdout}")
            print(f"   stderr: {e.stderr}")
            sys.exit(1)
    else:
        print("\n💡 Next steps:")
        print(f"   1. Review changes: git diff {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        print(f"   2. Commit & tag: python scripts/bump_version.py {part} --commit")
        print(f"   3. Or full release: python scripts/bump_version.py {part} --push --notes")


if __name__ == "__main__":
    main()
