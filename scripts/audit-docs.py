#!/usr/bin/env python3
"""KISS documentation consistency audit for CURRENT Local-miniMCP docs."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CURRENT_FILES = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CHANGELOG.md",
    DOCS / "README.md",
    DOCS / "admin-console.md",
    DOCS / "ai-clients.md",
    DOCS / "architecture.md",
    DOCS / "chatgpt-gate.md",
    DOCS / "client-grants.md",
    DOCS / "compatibility.md",
    DOCS / "configuration.md",
    DOCS / "controlled-write.md",
    DOCS / "deployment.md",
    DOCS / "diagrams.md",
    DOCS / "lifecycle.md",
    DOCS / "mcp-adapter.md",
    DOCS / "mission.md",
    DOCS / "project-state.md",
    DOCS / "roadmap.md",
    DOCS / "troubleshooting.md",
    DOCS / "tunnel-client-provenance.md",
] + sorted((DOCS / "runbooks").glob("*.md"))

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def operational_text(text: str) -> str:
    """Remove explicitly historical Markdown sections/lines before stale-state checks."""
    out: list[str] = []
    historical_level: int | None = None
    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).lower()
            if historical_level is not None and level <= historical_level:
                historical_level = None
            if any(word in title for word in ("histórico", "historical", "legacy snapshot")):
                historical_level = level
        if historical_level is not None:
            continue
        lower = line.lower()
        if "histórico:" in lower or "historical:" in lower:
            continue
        out.append(line)
    return "\n".join(out)


def main() -> int:
    errors: list[str] = []
    compat = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    version = str(compat["gateway_version"])
    catalog_version = int(compat["tool_catalog_version"])

    if manifest.get("version") != version:
        fail(errors, f"manifest version {manifest.get('version')} != compatibility {version}")
    if int(manifest.get("tool_catalog", -1)) != catalog_version:
        fail(errors, "manifest tool catalog version differs from compatibility.json")

    sys.path.insert(0, str(ROOT / "src"))
    from mcp_gateway.bridge import ALLOWED_TOOLS, get_catalog_metadata  # noqa: E402

    metadata = get_catalog_metadata(sorted(ALLOWED_TOOLS))
    if metadata["tool_count"] != 21:
        fail(errors, f"expected 21 tools, found {metadata['tool_count']}")
    if metadata["tool_catalog_version"] != catalog_version:
        fail(errors, "runtime tool catalog version differs from compatibility.json")
    for required in ("run_command", "run_task", "write_file", "gateway_doctor"):
        if required not in ALLOWED_TOOLS:
            fail(errors, f"required tool missing: {required}")

    stale_patterns = {
        "admin port 8080": re.compile(r"192\.168\.68\.55:8080|127\.0\.0\.1:8080"),
        "old gateway address": re.compile(r"192\.168\.68\.85"),
        "old admin account": re.compile(r"(?:Yorologo@|MCP_PI_USER[^\n]*Yorologo|Usuario[^\n]*Yorologo)"),
        "old tool count": re.compile(r"\b(?:9|14)\s+(?:active\s+)?deterministic\s+tools\b|Catalog contains (?:9|14) tools", re.I),
        "localhost-only admin": re.compile(r"localhost-only\s+Admin", re.I),
    }

    for path in CURRENT_FILES:
        if not path.exists():
            fail(errors, f"CURRENT document missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "file://" in text:
            fail(errors, f"local file:// link in {path.relative_to(ROOT)}")
        if path.name != "CHANGELOG.md":
            current = operational_text(text)
            for label, pattern in stale_patterns.items():
                if pattern.search(current):
                    fail(errors, f"{label} in CURRENT doc {path.relative_to(ROOT)}")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                fail(errors, f"link escapes repository in {path.relative_to(ROOT)}: {target}")
                continue
            if not resolved.exists():
                fail(errors, f"broken local link in {path.relative_to(ROOT)}: {target}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if version not in readme:
        fail(errors, f"README does not declare current version {version}")
    if "http://192.168.68.55" not in readme:
        fail(errors, "README missing current Admin LAN endpoint")

    if errors:
        print("DOCS_AUDIT=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("DOCS_AUDIT=PASS")
    print(f"gateway_version={version}")
    print(f"tool_catalog_version={catalog_version}")
    print(f"tool_count={metadata['tool_count']}")
    print(f"catalog_hash={metadata['catalog_hash']}")
    print(f"current_docs={len(CURRENT_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
