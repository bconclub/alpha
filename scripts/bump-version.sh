#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Auto version bump — called by git pre-commit hook
#
# Single Alpha version stored in engine/VERSION. Bumps on every
# commit regardless of which directory changed. Patch rolls over
# at 10:  0.0.9 → 0.1.0
#
# Also syncs dashboard/package.json to the same version.
# Both files are auto-staged so they're included in the commit.
# ═══════════════════════════════════════════════════════════════════

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
VERSION_FILE="$REPO_ROOT/engine/VERSION"
PKG_JSON="$REPO_ROOT/dashboard/package.json"

bump_version() {
    local current
    current=$(cat "$VERSION_FILE" 2>/dev/null || echo "0.0.0")

    IFS='.' read -r major minor patch <<< "$current"
    patch=$((patch + 1))

    if [ "$patch" -ge 10 ]; then
        patch=0
        minor=$((minor + 1))
    fi

    local new_version="$major.$minor.$patch"
    echo "$new_version" > "$VERSION_FILE"
    git add "$VERSION_FILE"

    # Sync dashboard/package.json version
    if [ -f "$PKG_JSON" ]; then
        sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$new_version\"/" "$PKG_JSON"
        git add "$PKG_JSON"
    fi

    echo "  Alpha: $current → $new_version"
}

# Skip if this is a version-only commit (prevent double-bump)
ONLY_VERSIONS=$(git diff --cached --name-only | grep -v 'VERSION' | grep -v 'package.json' | head -1 || true)
if [ -z "$ONLY_VERSIONS" ]; then
    exit 0
fi

echo "📦 Bumping Alpha version..."
bump_version
echo "✅ Version bump complete"
