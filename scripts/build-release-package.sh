#!/usr/bin/env bash
set -Eeuo pipefail

# Build the beginner-facing release bundle from one exact Git commit.
# The bundle contains the source tree plus a prebuilt Linux ARMv6 adapter so
# constrained appliances do not need Go just to install the Gateway.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SHA_INPUT="${1:-HEAD}"
OUTPUT_DIR="${2:-${ROOT}/dist}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

for cmd in git go tar gzip sha256sum python3; do
    command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

SHA="$(git -C "$ROOT" rev-parse "${SHA_INPUT}^{commit}")"
HEAD_SHA="$(git -C "$ROOT" rev-parse HEAD)"
[ "$SHA" = "$HEAD_SHA" ] || fail "release package commit must equal local HEAD ($HEAD_SHA)"
[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ] || fail "release packaging requires a clean worktree"

VERSION="$(git -C "$ROOT" show "$SHA:compatibility.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["gateway_version"])')"
SHORT="${SHA:0:12}"
if [ -n "${TMPDIR:-}" ]; then
    TMP_BASE="$TMPDIR"
elif [ -n "${PREFIX:-}" ]; then
    TMP_BASE="$PREFIX/tmp"
else
    TMP_BASE=/tmp
fi
mkdir -p "$TMP_BASE"
TMP="$(mktemp -d "$TMP_BASE/mcp-release.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PKG_ROOT="$TMP/MCP-Pi-${VERSION}"
mkdir -p "$PKG_ROOT" "$OUTPUT_DIR"

git -C "$ROOT" archive "$SHA" | tar -xf - -C "$PKG_ROOT"

(
    cd "$PKG_ROOT/mcp-adapter"
    CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=6 \
        go build -trimpath -ldflags='-s -w' -o "$PKG_ROOT/bin/mcp-gateway-adapter" .
)
chmod 0755 "$PKG_ROOT/bin/mcp-gateway-adapter" "$PKG_ROOT/install.sh" \
    "$PKG_ROOT/bin/mcp-gateway" "$PKG_ROOT/bin/mcp-gateway-client-stdio"

(
    cd "$PKG_ROOT"
    sha256sum \
        compatibility.json \
        manifest.json \
        install.sh \
        bin/mcp-gateway \
        bin/mcp-gateway-client-stdio \
        bin/mcp-gateway-adapter > SHA256SUMS
)

OUT="$OUTPUT_DIR/MCP-Pi-${VERSION}-linux-armv6-${SHORT}.tar.gz"
SOURCE_DATE_EPOCH="$(git -C "$ROOT" show -s --format=%ct "$SHA")"
tar -C "$TMP" --sort=name --mtime="@${SOURCE_DATE_EPOCH}" --owner=0 --group=0 --numeric-owner \
    -cf - "$(basename "$PKG_ROOT")" | gzip -n -9 > "$OUT"
PACKAGE_SHA="$(sha256sum "$OUT" | awk '{print $1}')"
ADAPTER_SHA="$(sha256sum "$PKG_ROOT/bin/mcp-gateway-adapter" | awk '{print $1}')"

echo "RELEASE_PACKAGE_BUILT"
echo "version=$VERSION"
echo "commit=$SHA"
echo "package=$OUT"
echo "package_sha256=$PACKAGE_SHA"
echo "adapter_sha256=$ADAPTER_SHA"
