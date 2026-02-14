#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Auto version bump — called by git pre-commit hook
#
# Detects which files are staged (engine/ or dashboard/) and bumps
# the corresponding VERSION file. Patch rolls over at 10:
#   2.0.9 → 2.1.0 → 2.1.1 → ... → 2.1.9 → 2.2.0
#
# Both VERSION files are auto-staged so they're included in the commit.
# ═══════════════════════════════════════════════════════════════════

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

bump_version() {
    local version_file="$1"
    local current
    current=$(cat "$version_file" 2>/dev/null || echo "2.0.0")

    IFS='.' read -r major minor patch <<< "$current"
    patch=$((patch + 1))

    if [ "$patch" -ge 10 ]; then
        patch=0
        minor=$((minor + 1))
    fi

    local new_version="$major.$minor.$patch"
    echo "$new_version" > "$version_file"
    git add "$version_file"
    echo "  Version: $current → $new_version ($version_file)"
}

# Check which paths are staged
ENGINE_STAGED=$(git diff --cached --name-only | grep '^engine/' | head -1 || true)
DASHBOARD_STAGED=$(git diff --cached --name-only | grep '^dashboard/' | head -1 || true)
SUPABASE_STAGED=$(git diff --cached --name-only | grep '^supabase/' | head -1 || true)

# Skip if this is a version-only commit (prevent double-bump)
ONLY_VERSIONS=$(git diff --cached --name-only | grep -v 'VERSION' | head -1 || true)
if [ -z "$ONLY_VERSIONS" ]; then
    exit 0
fi

BUMPED=false

if [ -n "$ENGINE_STAGED" ] || [ -n "$SUPABASE_STAGED" ]; then
    echo "📦 Bumping engine version..."
    bump_version "$REPO_ROOT/engine/VERSION"
    BUMPED=true
fi

if [ -n "$DASHBOARD_STAGED" ]; then
    echo "📦 Bumping dashboard version..."
    bump_version "$REPO_ROOT/dashboard/VERSION"
    BUMPED=true
fi

if [ "$BUMPED" = true ]; then
    echo "✅ Version bump complete"
fi
