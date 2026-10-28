# Version Management Guide

`main` is protected (pull request + green CI required), so a release is two steps:
the version bump travels through a PR, and the tag + GitHub Release are created
from `main` after the merge. `scripts/bump_version.py` automates both.

## Quick Start

```bash
# 1. Bump the version, generate notes, commit, push the branch, open a PR
python scripts/bump_version.py patch --pr

# 2. Merge the PR on GitHub once CI is green, then:
python scripts/bump_version.py release
```

Requirements: a clean working tree and the [GitHub CLI](https://cli.github.com/)
authenticated with `gh auth login` (`brew install gh` on macOS).

## Step 1: bump (`major` | `minor` | `patch`)

```bash
python scripts/bump_version.py patch            # only edit manifest.json
python scripts/bump_version.py patch -n         # + write RELEASE_NOTES_X.Y.Z.md
python scripts/bump_version.py patch -c         # + commit "Bump version to X.Y.Z"
python scripts/bump_version.py patch --pr       # + push the branch and open a PR
python scripts/bump_version.py patch --pr -d    # dry run: print the commands only
```

| Option | Short | Description |
|--------|-------|-------------|
| `--notes` | `-n` | Generate `RELEASE_NOTES_X.Y.Z.md` from commits since the last tag |
| `--commit` | `-c` | Commit the manifest and notes (implies `--notes`) |
| `--pr` / `--push` | `-p` | Commit, `git push -u` the branch and `gh pr create` against `main` |
| `--dry-run` | `-d` | Print the git/gh commands without running them |

Where the commit goes:
- on a feature branch — the bump is added to that branch (and its PR);
- on `main` — a `release/vX.Y.Z` branch is created first, `main` itself is never pushed.

The bump is refused if the target tag already exists locally or on GitHub.

## Step 2: release (after the merge)

```bash
python scripts/bump_version.py release          # tag, push tag, GitHub Release
python scripts/bump_version.py release -d       # dry run
python scripts/bump_version.py release --no-gh-release   # only push the tag
```

What it does:
1. checks the working tree is clean;
2. switches to `main` and runs `git pull --ff-only` (also in dry-run mode);
3. reads the version from `manifest.json` and checks that `vX.Y.Z` is not on GitHub yet;
4. creates the annotated tag `vX.Y.Z` on the merged commit and pushes **only that tag**;
5. runs `gh release create vX.Y.Z --verify-tag --notes-file RELEASE_NOTES_X.Y.Z.md`
   (if the notes file is missing, notes are generated on the fly and not committed).

If step 5 fails (e.g. `gh` isn't logged in), run `release` again: an existing local
tag on the same commit is reused.

## Version Types

- `major`: breaking changes (1.0.0 → 2.0.0)
- `minor`: new features (0.1.0 → 0.2.0)
- `patch`: bug fixes (0.1.0 → 0.1.1)

## Generated Release Notes

Commits since the previous tag are grouped by keywords in their subject:

- **✨ Features**: "feat", "add"
- **🐛 Bug Fixes**: "fix", "bug"
- **📝 Documentation**: "doc"
- **🔧 Other Changes**: everything else

`Bump version …` commits are skipped. The `Released:` date uses Kyiv time
regardless of the machine's time zone. Edit the file in the PR if the wording
needs polishing — `release` publishes whatever is merged.

```markdown
# Release 0.2.7

Released: 2025-12-26

## 🐛 Bug Fixes

- Fix sensor auto-updates with CoordinatorEntity

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
3. Clear browser cache if needed
```

## How HACS picks up a release

HACS offers the latest **GitHub Release** of the repository. A version bump
merged into `main` is therefore invisible to users until `release` has run.

## Troubleshooting

### `gh` not found / not authenticated
```bash
brew install gh
gh auth login
```

### Undo a bump before merging
Close the PR, delete the branch, or revert the bump commit on the branch.

### Undo a release
```bash
gh release delete vX.Y.Z --yes
git push origin :refs/tags/vX.Y.Z
git tag -d vX.Y.Z
```
Prefer releasing a new patch version over deleting a release users may already
have installed.

## Best Practices

1. Run `pre-commit run --all-files` and the tests before opening the PR.
2. Write descriptive commit subjects with prefixes (`fix:`, `feat:`, `docs:`) —
   they become the release notes.
3. Use semantic versioning correctly and mention breaking changes prominently.
