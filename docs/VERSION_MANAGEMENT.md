# Version Management Guide

## Quick Start

### Simple version bump (manual workflow)
```bash
python scripts/bump_version.py patch
# Then manually: git add, commit, tag, push
```

### Auto commit & tag
```bash
python scripts/bump_version.py patch --commit
# Then manually: git push origin main --tags
```

### Full automated release
```bash
python scripts/bump_version.py patch --push --notes
# Everything done: version updated, committed, tagged, pushed, notes generated
```

## Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--commit` | `-c` | Automatically commit changes and create git tag |
| `--push` | `-p` | Push commits and tags to GitHub (implies `--commit`) |
| `--notes` | `-n` | Generate release notes from commit messages |

## Version Types

- `major`: Breaking changes (1.0.0 → 2.0.0)
- `minor`: New features (0.1.0 → 0.2.0)
- `patch`: Bug fixes (0.1.0 → 0.1.1)

## Examples

### Example 1: Bug fix release (manual)
```bash
# Make your code changes
git add .
git commit -m "Fix sensor auto-updates"

# Bump version
python scripts/bump_version.py patch

# Review and push
git add custom_components/poltava_poweroff/manifest.json
git commit -m "Bump version to 0.2.7"
git tag -a v0.2.7 -m "Release 0.2.7"
git push origin main --tags
```

### Example 2: Bug fix release (automated)
```bash
# Make your code changes
git add .
git commit -m "Fix sensor auto-updates"

# One command to rule them all
python scripts/bump_version.py patch -p -n

# Result:
# ✅ Version updated: 0.2.6 → 0.2.7
# ✅ Release notes created: RELEASE_NOTES_0.2.7.md
# ✅ Committed: Bump version to 0.2.7
# ✅ Tagged: v0.2.7
# ✅ Pushed to GitHub
```

### Example 3: New feature release
```bash
# Make your code changes
git add .
git commit -m "Add support for multiple regions"

# Bump minor version with auto-push
python scripts/bump_version.py minor --push --notes

# Result: 0.2.6 → 0.3.0
```

## Release Workflow

### Recommended workflow:

1. **Develop feature/fix**
   ```bash
   git checkout -b feature/my-feature
   # Make changes...
   git commit -m "Add my feature"
   ```

2. **Merge to main**
   ```bash
   git checkout main
   git merge feature/my-feature
   ```

3. **Release**
   ```bash
   python scripts/bump_version.py patch -p -n
   ```

4. **Create GitHub Release** (manual step)
   - Go to: https://github.com/OLDIN/ha-poltava-poweroff/releases/new
   - Select tag: `v0.2.7`
   - Copy content from `RELEASE_NOTES_0.2.7.md`
   - Publish release

5. **HACS will detect new version**
   - Users will see `v0.2.7` instead of commit hash
   - "Update available" notification appears in HACS

## Generated Release Notes

The script automatically categorizes commits:

- **✨ Features**: Commits with "feat", "feature", "add", "added"
- **🐛 Bug Fixes**: Commits with "fix", "fixed", "bugfix", "bug"
- **📝 Documentation**: Commits with "doc", "docs", "documentation"
- **🔧 Other Changes**: Everything else

Example output saved to `RELEASE_NOTES_X.Y.Z.md`:

```markdown
# Release 0.2.7

Released: 2025-12-26

## 🐛 Bug Fixes

- Fix sensor auto-updates with CoordinatorEntity
- Fix midnight period handling

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
3. Clear browser cache if needed
```

## Troubleshooting

### Authentication errors when pushing
```bash
# Use SSH instead of HTTPS
git remote set-url origin git@github.com:OLDIN/ha-poltava-poweroff.git

# Or configure credential helper
git config credential.helper store
```

### Undo a version bump
```bash
# Before pushing
git reset --hard HEAD~1
git tag -d v0.2.7

# After pushing (not recommended)
git push origin :refs/tags/v0.2.7
git revert HEAD
```

## Best Practices

1. **Always test before releasing**
   - Run tests if available
   - Test in dev environment
   - Check linter: `pre-commit run --all-files`

2. **Write good commit messages**
   - Use prefixes: `fix:`, `feat:`, `docs:`
   - Be descriptive but concise
   - Reference issues: `fix: sensor updates (#42)`

3. **Use semantic versioning correctly**
   - **Patch**: Bug fixes, small improvements
   - **Minor**: New features, backward compatible
   - **Major**: Breaking changes

4. **Always create GitHub Releases**
   - Tags alone are not enough for HACS
   - Include release notes
   - Mention breaking changes prominently
