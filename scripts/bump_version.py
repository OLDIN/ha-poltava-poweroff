#!/usr/bin/env python3
"""Version bump and release helper for a protected ``main`` branch.

Two steps, matching the PR-based flow:

1. ``prepare`` (default): on a branch, bump ``manifest.json``, generate
   ``RELEASE_NOTES_X.Y.Z.md`` and commit. ``--pr`` also pushes the branch and
   opens a pull request. Nothing is ever pushed to ``main``.
2. After the PR is merged, ``.github/workflows/release.yml`` tags the merged
   commit and publishes the GitHub Release. ``release`` does the same locally
   (fast-forward ``main``, tag, push only the tag, ``gh release create``) and
   is the fallback when the workflow is not available.

Run without arguments for usage.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "custom_components" / "poltava_poweroff" / "manifest.json"
MAIN_BRANCH = "main"
REMOTE = "origin"
# Release dates are written in the project's local time, not the machine's.
RELEASE_TZ = ZoneInfo("Europe/Kyiv")
# gh is often installed outside the PATH of non-login shells.
GH_FALLBACK_PATHS = ("/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh")


class ReleaseError(Exception):
    """A precondition failed; the message tells the user what to do."""


# ---------------------------------------------------------------- helpers


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command in the repository root and capture its output."""
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=check)


def git(*args: str, check: bool = True) -> str:
    """Run git and return stripped stdout."""
    return run(["git", *args], check=check).stdout.strip()


class Runner:
    """Executes mutating commands, or only prints them in dry-run mode."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run

    def __call__(self, cmd: list[str]) -> None:
        shown = [Path(c).name if c == cmd[0] else c.replace(f"{REPO_ROOT}/", "") for c in cmd]
        printable = " ".join(f'"{c}"' if " " in c else c for c in shown)
        if self.dry_run:
            print(f"   [dry-run] {printable}")
            return
        print(f"   $ {printable}")
        result = run(cmd, check=False)
        if result.returncode != 0:
            raise ReleaseError(f"Command failed: {printable}\n{result.stderr.strip() or result.stdout.strip()}")


def find_gh() -> str | None:
    """Locate the GitHub CLI binary."""
    found = shutil.which("gh")
    if found:
        return found
    return next((p for p in GH_FALLBACK_PATHS if Path(p).exists()), None)


def github_repo() -> str:
    """Return ``owner/repo`` parsed from the origin remote URL."""
    url = git("remote", "get-url", REMOTE, check=False)
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?/?$", url)
    if not match:
        raise ReleaseError(f"Remote '{REMOTE}' is not a GitHub repository: {url!r}")
    return match.group(1)


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def ensure_clean_tree() -> None:
    """Refuse to run with uncommitted changes to tracked files."""
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ReleaseError("Working tree has uncommitted changes. Commit or stash them first.")


def get_current_version() -> str:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f).get("version", "0.0.0")


def update_manifest(version: str) -> None:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["version"] = version
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"✅ {MANIFEST_PATH.relative_to(REPO_ROOT)}: version → {version}")


def bump_version(current: str, part: str) -> str:
    """Bump a semantic version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", current)
    if not match:
        raise ValueError(f"Invalid version format: {current}. Expected X.Y.Z")
    major, minor, patch = map(int, match.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Invalid version part: {part}. Use major, minor or patch")


def notes_path(version: str) -> Path:
    return REPO_ROOT / f"RELEASE_NOTES_{version}.md"


def remote_tag_commit(tag: str) -> str | None:
    """Commit the tag points to on the remote (annotated tags are peeled)."""
    out = git("ls-remote", "--tags", REMOTE, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}", check=False)
    refs: dict[str, str] = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        refs[ref] = sha
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


def github_release_exists(gh: str, tag: str) -> bool:
    """Whether a GitHub Release for ``tag`` exists."""
    result = run([gh, "release", "view", tag, "--repo", github_repo(), "--json", "tagName"], check=False)
    if result.returncode == 0:
        return True
    if "release not found" in result.stderr.lower():
        return False
    raise ReleaseError(f"Cannot query GitHub Releases (is gh logged in? run gh auth login):\n{result.stderr.strip()}")


def tag_exists(tag: str) -> tuple[bool, bool]:
    """Return (exists locally, exists on the remote)."""
    local = bool(git("tag", "--list", tag))
    remote = bool(git("ls-remote", "--tags", REMOTE, f"refs/tags/{tag}", check=False))
    return local, remote


# ---------------------------------------------------------- release notes


def get_latest_tag(exclude: str | None = None) -> str | None:
    cmd = ["git", "describe", "--tags", "--abbrev=0"] + ([f"--exclude={exclude}"] if exclude else [])
    result = run(cmd, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def get_commits_since_tag(tag: str | None) -> list[str]:
    """Commit subjects since ``tag``, without version-bump commits."""
    rev = [f"{tag}..HEAD"] if tag else []
    out = git("log", *rev, "--pretty=format:%s")
    return [line for line in out.split("\n") if line and not line.startswith("Bump version")]


def generate_changelog(commits: list[str], version: str) -> str:
    """Build Markdown release notes grouped by commit-message keywords."""
    today = datetime.now(RELEASE_TZ).strftime("%Y-%m-%d")
    changelog = f"# Release {version}\n\nReleased: {today}\n\n"
    if not commits:
        return changelog + "No significant changes.\n"

    groups: dict[str, list[str]] = {
        "## ✨ Features": [],
        "## 🐛 Bug Fixes": [],
        "## 📝 Documentation": [],
        "## 🔧 Other Changes": [],
    }
    for commit in commits:
        lower = commit.lower()
        if any(w in lower for w in ("fix", "bug")):
            groups["## 🐛 Bug Fixes"].append(commit)
        elif any(w in lower for w in ("feat", "add")):
            groups["## ✨ Features"].append(commit)
        elif "doc" in lower:
            groups["## 📝 Documentation"].append(commit)
        else:
            groups["## 🔧 Other Changes"].append(commit)

    for title, items in groups.items():
        if items:
            changelog += f"{title}\n\n" + "".join(f"- {c}\n" for c in items) + "\n"

    changelog += (
        "## 🔄 Update Instructions\n\n"
        "1. Update via HACS or manually pull the latest version\n"
        "2. Restart Home Assistant\n"
        "3. Clear browser cache if needed\n"
    )
    return changelog


def write_notes(version: str) -> Path:
    changelog = generate_changelog(get_commits_since_tag(get_latest_tag()), version)
    path = notes_path(version)
    path.write_text(changelog, encoding="utf-8")
    print(f"✅ Created {path.relative_to(REPO_ROOT)}")
    print("─" * 60)
    print(changelog.rstrip())
    print("─" * 60)
    return path


# ---------------------------------------------------------------- prepare


def cmd_prepare(args: argparse.Namespace) -> None:
    """Bump the version on a branch; optionally commit, push and open a PR."""
    commit = args.commit or args.pr
    notes = args.notes or commit
    gh = find_gh() if args.pr else None
    if args.pr and not gh:
        raise ReleaseError("GitHub CLI (gh) not found. Install it (brew install gh) and run gh auth login.")
    if commit:
        ensure_clean_tree()

    current = get_current_version()
    new_version = bump_version(current, args.part)
    tag = f"v{new_version}"
    if any(tag_exists(tag)):
        raise ReleaseError(f"Tag {tag} already exists. Pick another version.")
    print(f"📦 {current} → {new_version}\n")

    execute = Runner(args.dry_run)
    branch = current_branch()
    if commit and branch == MAIN_BRANCH:
        # main is protected: the bump always travels through a PR.
        branch = f"release/{tag}"
        print(f"🌿 On {MAIN_BRANCH}: creating branch {branch}")
        execute(["git", "switch", "-c", branch])

    if args.dry_run:
        print(f"   [dry-run] would set version {new_version} and write {notes_path(new_version).name}")
    else:
        update_manifest(new_version)
        if notes:
            write_notes(new_version)

    if not commit:
        print("\n💡 Next: review the diff, commit it and open a PR. After the merge the")
        print("   Release workflow publishes it (fallback: python scripts/bump_version.py release)")
        return

    execute(["git", "add", str(MANIFEST_PATH), str(notes_path(new_version))])
    execute(["git", "commit", "-m", f"Bump version to {new_version}"])

    if args.pr:
        assert gh is not None
        execute(["git", "push", "-u", REMOTE, branch])
        execute(
            [
                gh,
                "pr",
                "create",
                "--repo",
                github_repo(),
                "--base",
                MAIN_BRANCH,
                "--head",
                branch,
                "--title",
                f"Release {new_version}",
                "--body-file",
                str(notes_path(new_version)),
            ]
        )
        print("\n✅ PR opened. Merge it once CI is green; the Release workflow then")
    else:
        print(f"\n✅ Committed on {branch}. Push it and open a PR; after the merge the Release workflow")
    print("   tags and publishes it (fallback: python scripts/bump_version.py release)")


# ---------------------------------------------------------------- release


def cmd_release(args: argparse.Namespace) -> None:
    """Tag the merged version on main, push the tag and create the release."""
    ensure_clean_tree()
    gh = find_gh()
    if not gh and not args.no_gh_release:
        raise ReleaseError(
            "GitHub CLI (gh) not found. Install it (brew install gh) and run gh auth login, "
            "or pass --no-gh-release to only push the tag."
        )

    execute = Runner(args.dry_run)
    print(f"🔄 Updating {MAIN_BRANCH}")
    # Switching branches and fast-forwarding are safe to run even in dry-run.
    run(["git", "switch", MAIN_BRANCH])
    pull = run(["git", "pull", "--ff-only", REMOTE, MAIN_BRANCH], check=False)
    if pull.returncode != 0:
        raise ReleaseError(f"Cannot fast-forward {MAIN_BRANCH}:\n{pull.stderr.strip()}")

    head = git("rev-parse", "HEAD")
    if head != git("rev-parse", f"{REMOTE}/{MAIN_BRANCH}"):
        raise ReleaseError(f"Local {MAIN_BRANCH} differs from {REMOTE}/{MAIN_BRANCH}. Sync it first.")

    version = get_current_version()
    tag = f"v{version}"
    local = bool(git("tag", "--list", tag))
    remote_commit = remote_tag_commit(tag)
    if remote_commit:
        # The tag is already on GitHub: either fully released (nothing to do),
        # or a previous run / the workflow pushed it and the release step failed.
        if args.no_gh_release or (gh and github_release_exists(gh, tag)):
            raise ReleaseError(
                f"{tag} is already released (the Release workflow does it right after the merge). "
                "For a new release bump the version in a PR first (python scripts/bump_version.py patch --pr)."
            )
        if remote_commit != head:
            raise ReleaseError(
                f"Tag {tag} on {REMOTE} points to {remote_commit[:7]}, not {MAIN_BRANCH} ({head[:7]}). "
                "Fix the tag manually or bump the version."
            )
        print(f"↩️  Tag {tag} is already on {REMOTE} but has no GitHub Release; creating only the release")
    elif local:
        tagged = git("rev-list", "-n", "1", tag)
        if tagged != head:
            raise ReleaseError(f"Local tag {tag} points to {tagged[:7]}, not {head[:7]}. Delete it: git tag -d {tag}")

    notes = notes_path(version)
    temp_notes = False
    if not notes.exists():
        print(f"⚠️  {notes.name} is not in the repo; generating notes for the release only")
        changelog = generate_changelog(get_commits_since_tag(get_latest_tag(exclude=tag)), version)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(changelog)
        notes = Path(f.name)
        temp_notes = True

    subject = git("log", "-1", "--format=%h %s")
    print(f"🏷️  Releasing {tag} at {subject}")

    try:
        if not remote_commit:
            if not local:
                execute(["git", "tag", "-a", tag, "-m", f"Release {version}"])
            execute(["git", "push", REMOTE, f"refs/tags/{tag}"])
        if args.no_gh_release:
            print(f"\n✅ Tag {tag} pushed (GitHub Release skipped)")
            return
        assert gh is not None
        execute(
            [
                gh,
                "release",
                "create",
                tag,
                "--repo",
                github_repo(),
                "--verify-tag",
                "--title",
                tag,
                "--notes-file",
                str(notes),
            ]
        )
    finally:
        if temp_notes:
            notes.unlink(missing_ok=True)

    if not args.dry_run:
        print(f"\n🎉 Released {tag}: https://github.com/{github_repo()}/releases/tag/{tag}")


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bump_version.py",
        description="Bump the integration version in a PR, then tag and release it after the merge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python scripts/bump_version.py patch --pr      # bump, notes, commit, push branch, open PR\n"
            "  python scripts/bump_version.py minor -c        # same, but stop after the commit\n"
            "  python scripts/bump_version.py patch           # only edit manifest.json\n"
            "  python scripts/bump_version.py release         # fallback after merge: tag main, push tag, GitHub Release\n"
            "  python scripts/bump_version.py release -d      # show what release would do\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    for part in ("major", "minor", "patch"):
        p = sub.add_parser(part, help=f"bump the {part} version (run on a branch or on {MAIN_BRANCH})")
        p.set_defaults(func=cmd_prepare, part=part)
        p.add_argument("-n", "--notes", action="store_true", help="generate RELEASE_NOTES_X.Y.Z.md")
        p.add_argument(
            "-c",
            "--commit",
            action="store_true",
            help=f"commit the bump (implies --notes; creates release/vX.Y.Z when on {MAIN_BRANCH})",
        )
        p.add_argument(
            "--pr",
            "-p",
            "--push",
            dest="pr",
            action="store_true",
            help="commit, push the branch and open a pull request (needs gh)",
        )
        p.add_argument("-d", "--dry-run", action="store_true", help="print git/gh commands instead of running them")

    r = sub.add_parser("release", help=f"after merge: tag {MAIN_BRANCH}, push the tag, create the GitHub Release")
    r.set_defaults(func=cmd_release)
    r.add_argument("--no-gh-release", action="store_true", help="only push the tag, skip gh release create")
    r.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help=f"print the tag/push/release commands only (still switches to and fast-forwards {MAIN_BRANCH})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-r" in argv or "--release" in argv:
        print("ℹ️  -r/--release is gone: releases are created after the PR merge with")
        print("   python scripts/bump_version.py release\n")
        argv = [a for a in argv if a not in ("-r", "--release")]

    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        print(f"Current version: {get_current_version()}\n")
        parser.print_help()
        if not find_gh():
            print("\n⚠️  GitHub CLI (gh) not found: brew install gh && gh auth login")
        return 1

    try:
        args.func(args)
    except ReleaseError as err:
        print(f"\n❌ {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
