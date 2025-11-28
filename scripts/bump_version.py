#!/usr/bin/env python3
"""Script to bump version in manifest.json following semantic versioning."""

import json
import re
import sys
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent.parent / "custom_components" / "poltava_poweroff" / "manifest.json"


def get_current_version() -> str:
    """Get current version from manifest.json."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest.get("version", "0.0.0")


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

    print(f"✅ Updated version in {MANIFEST_PATH} to {version}")


def main() -> None:
    """Main function."""
    if len(sys.argv) < 2:
        current = get_current_version()
        print(f"Current version: {current}")
        print("\nUsage: python scripts/bump_version.py <major|minor|patch>")
        print("\nExamples:")
        print("  python scripts/bump_version.py patch  # 0.1.0 -> 0.1.1")
        print("  python scripts/bump_version.py minor   # 0.1.0 -> 0.2.0")
        print("  python scripts/bump_version.py major   # 0.1.0 -> 1.0.0")
        sys.exit(1)

    part = sys.argv[1].lower()
    if part not in ("major", "minor", "patch"):
        print(f"❌ Error: Invalid version part '{part}'. Use 'major', 'minor', or 'patch'")
        sys.exit(1)

    current = get_current_version()
    new_version = bump_version(current, part)

    print(f"Current version: {current}")
    print(f"New version: {new_version}")
    print()

    update_manifest(new_version)
    print("\n💡 Next steps:")
    print(f"   1. Review changes: git diff {MANIFEST_PATH}")
    print(f"   2. Commit: git commit -m 'Bump version to {new_version}' {MANIFEST_PATH}")
    print(f"   3. Tag release: git tag -a v{new_version} -m 'Release {new_version}'")
    print("   4. Push: git push origin main --tags")


if __name__ == "__main__":
    main()
