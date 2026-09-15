# Consolidación documental MCP-Pi Gateway v1.2.1 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alinear toda la documentación con MCP-Pi Gateway v1.2.1 y entregar un manual reproducible de instalación limpia en Debian 13 Trixie, con requisitos, tecnologías, diagramas Mermaid y opcionales claramente identificados.

**Architecture:** Markdown continúa siendo la única fuente documental y Mermaid la única notación gráfica. `README.md` será la portada, `docs/architecture.md` la autoridad arquitectónica, `docs/project-state.md` el estado dinámico, `docs/installation.md` el recorrido de instalación y `docs/runbooks/` los procedimientos; un comprobador pequeño en Python estándar hará cumplir los contratos transversales.

**Tech Stack:** Markdown, Mermaid, Python 3.9+ estándar, Git, comandos POSIX existentes, suite `unittest`, Go 1.27.1/MCP Go SDK 1.7.0 y Tailwind CSS 3.4.x únicamente para verificar los cambios frontend ya presentes.

**Spec:** `docs/superpowers/specs/2026-09-13-documentacion-v1.2.1-design.md`

## Global Constraints

- Baseline vigente: Gateway `1.2.1`, release `v1.2.1`, Core API `1`, Bridge API `1`, Tool Catalog `3`, Registry Schema `1`, MCP `2026-07-28`, MCP legacy `2025-11-25`, Go SDK `1.7.0` y 14 herramientas.
- Producción vigente: Raspberry Pi OS / Debian 13 Trixie `armv6l`; Debian 11 Bullseye se conserva sólo como rollback físico histórico.
- Python mínimo: `3.9`; UID, GID e IP observados no son requisitos universales ni identidad.
- Mantener Admin en `127.0.0.1:8080` y MCP en `127.0.0.1:8090/mcp`; no documentar exposición pública directa.
- Mantener `StrictHostKeyChecking=yes`, pinning criptográfico, least privilege, deny-by-default y fail-closed.
- No modificar runtime, Registry, red, dispositivos, identidades, tags ni evidencia histórica.
- No añadir generadores documentales, frameworks ni dependencias.
- Marcar cada integración, restore, build, rescate o rollback no esencial con `> **OPCIONAL**`.
- Preservar los cambios frontend ya presentes y no incluirlos en commits documentales salvo en el gate final de verificación.

---

### Task 1: Contrato documental ejecutable

**Files:**
- Create: `scripts/check_docs.py`
- Create: `tests/test_documentation.py`

**Interfaces:**
- Consumes: `compatibility.json`, archivos Markdown rastreados bajo la raíz y el catálogo real de `src/mcp_gateway/bridge.py`.
- Produces: `check_repository(root: Path) -> list[str]` y un CLI que devuelve `0` sin errores o `1` mostrando un error por línea.

- [ ] **Step 1: Escribir pruebas que describan los controles**

Crear `tests/test_documentation.py` con temporales autocontenidos para enlace roto, fence abierto, `file://`, bypass SSH, baseline obsoleto, catálogo incorrecto, IP presentada como identidad y caso válido:

```python
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts" / "check_docs.py")
check_docs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_docs)


class DocumentationChecksTest(unittest.TestCase):
    def make_repo(self, markdown: str) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "README.md").write_text(markdown, encoding="utf-8")
        (root / "compatibility.json").write_text(json.dumps({
            "gateway_version": "1.2.1",
            "core_api_version": 1,
            "bridge_api_version": 1,
            "tool_catalog_version": 3,
            "registry_schema_version": 1,
            "mcp": {"version": "1.7.0", "protocol": "2026-07-28", "protocol_legacy": "2025-11-25"},
        }), encoding="utf-8")
        return root

    def test_accepts_valid_markdown(self):
        root = self.make_repo("# Gateway 1.2.1\n\n[estado](../../../compatibility.json)\n")
        self.assertEqual(check_docs.check_repository(root), [])

    def test_reports_broken_link_and_open_fence(self):
        root = self.make_repo("# Gateway 1.2.1\n\n[ausente](../../no.md)\n\n```sh\necho ok\n")
        errors = "\n".join(check_docs.check_repository(root))
        self.assertIn("enlace interno inexistente", errors)
        self.assertIn("bloque de código sin cierre", errors)

    def test_reports_unsafe_local_links_and_ssh_bypass(self):
        root = self.make_repo("# Gateway 1.2.1\n\n[file](file:///tmp/x)\n\n`StrictHostKeyChecking=no`\n")
        errors = "\n".join(check_docs.check_repository(root))
        self.assertIn("file://", errors)
        self.assertIn("host-key checking", errors)

    def test_reports_stale_current_baseline_and_ip_identity(self):
        root = self.make_repo("# Estado actual de v1.0.1\n\nLa IP fija es la identidad del Target.\n")
        errors = "\n".join(check_docs.check_repository(root))
        self.assertIn("v1.0.1 presentado como vigente", errors)
        self.assertIn("IP presentada como identidad", errors)

    def test_reports_wrong_tool_count(self):
        root = self.make_repo("# Gateway 1.2.1\n")
        bridge = root / "src" / "mcp_gateway" / "bridge.py"
        bridge.parent.mkdir(parents=True)
        bridge.write_text("ALLOWED_TOOLS = {'a', 'b'}\n", encoding="utf-8")
        self.assertIn("catálogo real contiene 2 herramientas", "\n".join(check_docs.check_repository(root)))
```

- [ ] **Step 2: Ejecutar las pruebas y comprobar el fallo inicial**

Run: `python3 -m unittest -v tests.test_documentation`

Expected: `FileNotFoundError` para `scripts/check_docs.py`.

- [ ] **Step 3: Implementar el comprobador mínimo**

Crear `scripts/check_docs.py` usando sólo `argparse`, `ast`, `json`, `pathlib`, `re` y `sys`. Debe excluir `docs/superpowers/`, que contiene patrones de prueba y decisiones de diseño, y validar además baseline vigente, relación IP/identidad y el conjunto real `ALLOWED_TOOLS`:

```python
CANONICAL = {
    "gateway_version": "1.2.1",
    "core_api_version": 1,
    "bridge_api_version": 1,
    "tool_catalog_version": 3,
    "registry_schema_version": 1,
}
MCP_CANONICAL = {"version": "1.7.0", "protocol": "2026-07-28", "protocol_legacy": "2025-11-25"}
CURRENT_DOCS = (
    "README.md", "AGENTS.md", "docs/architecture.md", "docs/compatibility.md",
    "docs/installation.md", "docs/technologies.md", "docs/project-state.md",
)
CURRENT_SNIPPETS = ("v1.2.1", "Core API", "Bridge API", "Tool Catalog", "Registry Schema", "2026-07-28", "2025-11-25", "1.7.0", "14")
UNSAFE_SSH = re.compile(r"StrictHostKeyChecking\s*(?:=|\s)\s*(?:no|accept-new)", re.I)
LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
STALE_CURRENT = re.compile(r"(?:actual|vigente|current)[^\n]{0,40}v1\.0\.1|v1\.0\.1[^\n]{0,40}(?:actual|vigente|current)", re.I)
IP_AS_IDENTITY = re.compile(r"IP fija\s+(?:es|equivale a)\s+la identidad", re.I)


def markdown_files(root: Path) -> list[Path]:
    paths = [root / "README.md", root / "AGENTS.md"]
    paths.extend(path for path in (root / "docs").rglob("*.md") if "superpowers" not in path.parts)
    return sorted(path for path in paths if path.is_file())


def check_repository(root: Path) -> list[str]:
    errors: list[str] = []
    contract = json.loads((root / "compatibility.json").read_text(encoding="utf-8"))
    for key, expected in CANONICAL.items():
        if contract.get(key) != expected:
            errors.append(f"compatibility.json: {key}={contract.get(key)!r}; esperado {expected!r}")
    for key, expected in MCP_CANONICAL.items():
        actual = contract.get("mcp", {}).get(key)
        if actual != expected:
            errors.append(f"compatibility.json: mcp.{key}={actual!r}; esperado {expected!r}")
    if (root / "docs" / "architecture.md").is_file():
        for name in CURRENT_DOCS:
            path = root / name
            if not path.is_file():
                errors.append(f"{name}: documento canónico inexistente")
                continue
            text = path.read_text(encoding="utf-8")
            for snippet in CURRENT_SNIPPETS:
                if snippet not in text:
                    errors.append(f"{name}: falta contrato canónico {snippet!r}")
    bridge = root / "src" / "mcp_gateway" / "bridge.py"
    if bridge.is_file():
        tree = ast.parse(bridge.read_text(encoding="utf-8"))
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ALLOWED_TOOLS" for target in node.targets))
        tool_count = len(ast.literal_eval(assignment.value))
        if tool_count != 14:
            errors.append(f"{bridge.relative_to(root)}: catálogo real contiene {tool_count} herramientas; esperadas 14")
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root)
        historical = relative.parts[:2] in {("docs", "releases"), ("docs", "inventory"), ("docs", "migration")} or relative == Path("docs/v1-acceptance.md")
        if text.count("```") % 2:
            errors.append(f"{relative}: bloque de código sin cierre")
        if "file://" in text:
            errors.append(f"{relative}: enlace local file:// no permitido")
        for line_number, line in enumerate(text.splitlines(), 1):
            if UNSAFE_SSH.search(line) and "docs-check: prohibited-example" not in line:
                errors.append(f"{relative}:{line_number}: bypass de host-key checking no permitido")
        if not historical and STALE_CURRENT.search(text):
            errors.append(f"{relative}: v1.0.1 presentado como vigente")
        if not historical and IP_AS_IDENTITY.search(text):
            errors.append(f"{relative}: IP presentada como identidad")
        for target in LINK.findall(text):
            clean = target.split("#", 1)[0].strip().strip("<>")
            if not clean or re.match(r"(?:https?|mailto):", clean):
                continue
            if not (path.parent / clean).resolve().exists():
                errors.append(f"{relative}: enlace interno inexistente: {target}")
    return errors
```

Añadir `main()` para aceptar `--root`, imprimir `PASS: documentación consistente` cuando no haya errores y terminar con `raise SystemExit(main())`.

- [ ] **Step 4: Ejecutar pruebas unitarias y el diagnóstico sobre el árbol actual**

Run: `python3 -m unittest -v tests.test_documentation`

Expected: 5 tests `OK`.

Run: `python3 scripts/check_docs.py`

Expected: `FAIL` con enlaces/bypasses/inconsistencias reales que las tareas siguientes corregirán.

- [ ] **Step 5: Crear checkpoint del validador**

```bash
git add scripts/check_docs.py tests/test_documentation.py
git commit -m "test: add documentation consistency gate"
```

---

### Task 2: Portada, misión y mapa de autoridad

**Files:**
- Modify: `README.md`
- Modify: `docs/mission.md`

**Interfaces:**
- Consumes: baseline de `compatibility.json`, estado de `docs/project-state.md` y arquitectura de `docs/architecture.md`.
- Produces: una portada vigente y un mapa de navegación que todos los documentos especializados pueden enlazar.

- [ ] **Step 1: Registrar el fallo de baseline antes de editar**

Run: `rg -n "Estado oficial de v1\.0\.1|Bullseye.*producción|catálogo v2|9 herramientas" README.md docs/mission.md`

Expected: al menos una coincidencia obsoleta en `README.md`.

- [ ] **Step 2: Reemplazar el README monolítico por una portada mantenible**

Reescribir `README.md` con estas secciones y datos exactos:

```markdown
# MCP-Pi Gateway

MCP-Pi Gateway v1.2.1 convierte una Raspberry Pi ligera en una frontera de autenticación, autorización, auditoría y delegación entre clientes MCP y Targets autorizados.

## Baseline vigente

| Contrato | Valor |
|---|---|
| Release estable | `v1.2.1` |
| Producción | Debian 13 Trixie, `armv6l` |
| Core API / Bridge API | `1` / `1` |
| Tool Catalog | 3 — 14 herramientas de alto nivel |
| Registry Schema | `1` |
| MCP | `2026-07-28` (legacy `2025-11-25`) |
| MCP Go SDK | `1.7.0` |
| Admin | `127.0.0.1:8080` |
| Endpoint MCP | `127.0.0.1:8090/mcp` |

## Inicio rápido

Para una instalación nueva, seguir [Instalación paso a paso](../../deployment.md). La restauración histórica y las integraciones cloud están marcadas como opcionales.
```

Completar únicamente: propósito, diagrama de contexto pequeño, garantías, inicio rápido, tecnologías principales, estado, mapa documental, desarrollo/verificación, releases y licencia. Enlazar en vez de duplicar procedimientos.

- [ ] **Step 3: Alinear la misión sin convertirla en estado dinámico**

Conservar visión, roles y principios en `docs/mission.md`; retirar endpoints y cronologías duplicadas. Añadir enlaces a `README.md`, `docs/architecture.md` y `docs/project-state.md`, y mantener cloud ingress como capacidad opcional, nunca requisito del producto local.

- [ ] **Step 4: Verificar navegación y baseline**

Run: `python3 scripts/check_docs.py`

Expected: ya no reporta `README.md`; puede seguir fallando por documentos aún no tratados.

Run: `rg -n "v1\.0\.1.*(actual|vigente|current)|Bullseye.*producción" README.md docs/mission.md`

Expected: sin coincidencias que presenten esos valores como vigentes.

- [ ] **Step 5: Crear checkpoint de portada**

```bash
git add README.md docs/mission.md
git commit -m "docs: establish v1.2.1 documentation portal"
```

---

### Task 3: Manual completo de instalación y matriz tecnológica

**Files:**
- Create: `docs/installation.md`
- Create: `docs/technologies.md`
- Modify: `docs/runbooks/install.md`

**Interfaces:**
- Consumes: `install.sh`, `manifest.json`, `compatibility.json`, layout `/home/mcp-gateway`, unidades de `config/systemd/` y comandos reales de `bin/mcp-gateway`.
- Produces: procedimiento canónico de instalación limpia; `docs/runbooks/install.md` queda como entrada breve compatible que dirige al manual.

- [ ] **Step 1: Inventariar comandos y archivos que el manual puede afirmar**

Run: `find config/systemd -maxdepth 1 -type f -print | sort && ./bin/mcp-gateway --help && ./bin/mcp-gateway setup --help && ./bin/mcp-gateway doctor --help`

Expected: lista real de unidades y ayuda de CLI; copiar al manual sólo opciones observadas.

- [ ] **Step 2: Crear la instalación principal con contrato repetible**

Escribir `docs/installation.md` en español. En cada etapa usar exactamente:

```markdown
### Etapa N — nombre

**OBJECTIVE**

Resultado concreto de la etapa.

**REQUIREMENTS**

Prerrequisitos verificables.

**COMMANDS**

Comandos copiables sin secretos reales.

**EXPECTED EVIDENCE**

Salida, listener, propietario, checksum o gate observable.

**STOP CONDITIONS**

Condiciones de identidad, permisos, checksum, schema o exposición que obligan a detenerse.

**ROLLBACK**

Cómo volver al estado anterior sin perder datos.
```

Cubrir: tabla compacta de todos los contratos canónicos; topología; hardware mínimo/recomendado; Raspberry Pi OS Lite 32-bit Trixie; `yorologo`; red privada; fingerprint SSH; descarga/verificación v1.2.1; usuario `mcp-gateway`; despliegue en `/home/mcp-gateway/mcp-gateway`; `sudo ./install.sh`; Registry; servicios loopback; Target/Project/Client/Grant; pruebas positivas/negativas; reboot; backup; troubleshooting y checklist final.

- [ ] **Step 3: Marcar todos los caminos no esenciales como opcionales**

Usar esta cabecera en cada uno de los nueve apartados opcionales:

```markdown
> **OPCIONAL — no bloquea la instalación local mínima.**
>
> Activar sólo si se necesita esta integración. El apartado declara sus prerrequisitos, riesgo, efecto y gate independiente.
```

Aplicarla a Termux Target, build Go, build Tailwind, Secure MCP Tunnel, clientes adicionales, identidad histórica, Registry histórico, USB tethering, rollback Bullseye y empaquetado/desarrollo de releases.

- [ ] **Step 4: Crear la matriz de tecnologías**

Escribir `docs/technologies.md` con una tabla inicial de contratos y otra con columnas `Tecnología`, `Versión`, `Capa`, `Tipo`, `Uso`, `Razón` e `Impacto ARMv6`. Incluir Python 3.9+, Flask/Jinja2, SQLite, OpenSSH, systemd, Go 1.27.1 del módulo, MCP Go SDK 1.7.0, Tailwind 3.4.x, HTMX, POSIX shell, Git y Secure MCP Tunnel; etiquetar build-time y opcionales sin convertirlos en requisitos de runtime.

- [ ] **Step 5: Convertir el runbook antiguo en un índice compatible**

Reducir `docs/runbooks/install.md` a propósito, prerrequisitos breves, enlace al manual canónico y una verificación rápida. No conservar UID 1001 como requisito ni `Yorologo` con mayúscula.

- [ ] **Step 6: Verificar comandos, opcionales y enlaces**

Run: `rg -n '^> \*\*OPCIONAL' docs/installation.md docs/technologies.md`

Expected: todos los caminos opcionales tienen etiqueta visible.

Run: `rg -n 'Yorologo|UID.?1001|file://' docs/installation.md docs/technologies.md docs/runbooks/install.md`

Expected: sin coincidencias operativas obsoletas.

Run: `python3 scripts/check_docs.py`

Expected: sin errores para los tres archivos de esta tarea.

- [ ] **Step 7: Crear checkpoint del manual**

```bash
git add docs/installation.md docs/technologies.md docs/runbooks/install.md
git commit -m "docs: add complete v1.2.1 installation manual"
```

---

### Task 4: Arquitectura y diagramas Mermaid canónicos

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/compatibility.md`

**Interfaces:**
- Consumes: clases/tablas reales de `src/mcp_gateway`, catálogo de `bridge.py`, `compatibility.json`, servicios systemd y esquema SQLite.
- Produces: autoridad arquitectónica con 12 diagramas Mermaid y explicación textual equivalente.

- [ ] **Step 1: Comprobar componentes y relaciones contra código**

Run: `rg -n '^class |CREATE TABLE|ALLOWED_TOOLS|TOOL_CAPABILITIES' src/mcp_gateway`

Expected: nombres reales para Core/Tools, Policy, Registry, entidades y catálogo; no inventar clases o tablas.

- [ ] **Step 2: Consolidar arquitectura actual**

Reestructurar `docs/architecture.md` en: tabla de contratos canónicos; contexto; términos; Single Core; fronteras de confianza; despliegue/puertos; componentes; Registry; autorización; transporte SSH; controlled writes; kill switches; lifecycle; recuperación y decisiones. Corregir catálogo v3/14 herramientas y `apply_patch` vigente.

- [ ] **Step 3: Añadir los diagramas requeridos con texto equivalente**

Incluir bloques Mermaid para:

```text
flowchart: contexto, despliegue/fronteras, update/rollback, recuperación física
classDiagram: Core, Policy, Registry, Tools, SSH Transport y adapters
erDiagram: Target, Project, Client, Grant, Activity, Settings y AdminUser
sequenceDiagram: autorización MCP, ejecución remota, recuperación DHCP, acceso Admin
stateDiagram-v2: kill switches e instalación
```

Antes o después de cada bloque, explicar actores, flechas, decisión fail-closed y resultado para lectores sin render Mermaid. Las IP deben aparecer sólo como ejemplos/observaciones.

- [ ] **Step 4: Alinear la especificación de compatibilidad**

Actualizar `docs/compatibility.md` a los valores exactos de `compatibility.json`, explicar negociación MCP actual/legacy, 14 herramientas, request IDs, auth y fail-closed. Enlazar detalles arquitectónicos en vez de copiarlos.

- [ ] **Step 5: Validar cantidad, tipos y fences Mermaid**

Run: `rg -n '^```mermaid|^(flowchart|classDiagram|erDiagram|sequenceDiagram|stateDiagram-v2)' docs/architecture.md`

Expected: 12 bloques y presencia de los cinco tipos requeridos.

Run: `python3 scripts/check_docs.py`

Expected: sin errores para arquitectura/compatibilidad; otros documentos pueden seguir pendientes.

- [ ] **Step 6: Crear checkpoint arquitectónico**

```bash
git add docs/architecture.md docs/compatibility.md
git commit -m "docs: align architecture and Mermaid diagrams"
```

---

### Task 5: Contrato operativo y estado dinámico

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/project-state.md`

**Interfaces:**
- Consumes: baseline y modelo de autoridad ya documentados.
- Produces: contrato operativo sin baseline v1.0.1 contradictorio y estado cronológico separado de arquitectura/procedimientos.

- [ ] **Step 1: Detectar contradicciones actuales**

Run: `rg -n 'current software baseline|release actual|Runtime esperado de v1\.0\.1|software baseline: v1\.0\.1|192\.168\.68\.(55|72|84|85)' AGENTS.md docs/project-state.md`

Expected: evidencia de referencias conflictivas que deben clasificarse como actuales, observadas o históricas.

- [ ] **Step 2: Corregir AGENTS sin convertirlo en changelog**

Mantener una tabla compacta de contratos, invariantes y STOP conditions. Corregir todas las declaraciones actuales a v1.2.1, renombrar el runtime esperado, conservar v1.0.1 sólo en historia/rollback, y enlazar `docs/project-state.md`, `docs/architecture.md`, `docs/installation.md` y releases. Etiquetar IP/UID observados con fecha o como no universales.

- [ ] **Step 3: Reducir project-state al estado vigente y cronología necesaria**

Conservar tabla compacta de contratos, fase `POST_V1_OPERATION_AND_MAINTENANCE`, release v1.2.1, Trixie promovido, gates, último estado observado y próxima acción. Mover explicaciones arquitectónicas a enlaces. Resolver endpoints conflictivos usando el dato más reciente ya evidenciado en el documento, marcado como observación mutable y no identidad.

- [ ] **Step 4: Verificar autoridad y baseline**

Run: `rg -n 'v1\.0\.1.*(actual|vigente|current)|Runtime esperado de v1\.0\.1' AGENTS.md docs/project-state.md`

Expected: sin coincidencias vigentes; v1.0.1 sólo aparece con contexto histórico.

Run: `python3 scripts/check_docs.py`

Expected: sin errores atribuibles a estos dos archivos.

- [ ] **Step 5: Crear checkpoint operativo**

```bash
git add AGENTS.md docs/project-state.md
git commit -m "docs: align operational contract and current state"
```

---

### Task 6: Documentos técnicos especializados

**Files:**
- Modify: `docs/admin-console.md`
- Modify: `docs/ai-clients.md`
- Modify: `docs/chatgpt-gate.md`
- Modify: `docs/client-grants.md`
- Modify: `docs/controlled-write.md`
- Modify: `docs/gateway-mvp.md`
- Modify: `docs/lifecycle.md`
- Modify: `docs/mcp-adapter.md`
- Modify: `docs/os-migration.md`
- Modify: `docs/tunnel-client-provenance.md`

**Interfaces:**
- Consumes: README, arquitectura, instalación, tecnologías y estado ya consolidados.
- Produces: documentos acotados a su dominio, sin duplicar baseline ni procedimientos.

- [ ] **Step 1: Localizar deuda transversal en el grupo**

Run: `rg -n 'v1\.0\.1|Bullseye|catalog.*2|9 tools|9 herramientas|pc-local|StrictHostKeyChecking|192\.168\.68\.' docs/{admin-console,ai-clients,chatgpt-gate,client-grants,controlled-write,gateway-mvp,lifecycle,mcp-adapter,os-migration,tunnel-client-provenance}.md`

Expected: lista revisable; cada coincidencia se conserva con etiqueta histórica/opcional o se corrige.

- [ ] **Step 2: Alinear cada documento con su única responsabilidad**

Aplicar esta matriz:

| Archivo | Responsabilidad que permanece |
|---|---|
| `admin-console.md` | funciones, seguridad y accesibilidad de Admin |
| `ai-clients.md` | identidades, auth y grants de clientes |
| `chatgpt-gate.md` | gate opcional de Secure MCP Tunnel |
| `client-grants.md` | modelo y evaluación de grants |
| `controlled-write.md` | `write_file`, `apply_patch`, backups y switches |
| `gateway-mvp.md` | contexto histórico de Phase 4A con cabecera histórica |
| `lifecycle.md` | instalación/update/rollback como modelo; procedimientos por enlace |
| `mcp-adapter.md` | protocolo, bridge, transportes y 14 herramientas |
| `os-migration.md` | evidencia/procedimiento de Phase 8 ya cerrada |
| `tunnel-client-provenance.md` | procedencia y build opcional del tunnel client |

Añadir `> **OPCIONAL**` en ChatGPT/tunnel y build; usar `termux-main`/`termux-local`; eliminar cualquier bypass SSH operativo.

- [ ] **Step 3: Verificar duplicación y contratos**

Run: `rg -n 'catalog.*2|9 tools|9 herramientas|StrictHostKeyChecking=(no|accept-new)|pc-local' docs/{admin-console,ai-clients,chatgpt-gate,client-grants,controlled-write,gateway-mvp,lifecycle,mcp-adapter,os-migration,tunnel-client-provenance}.md`

Expected: sin recomendaciones vigentes obsoletas; `pc-local` sólo puede aparecer como alias histórico desaconsejado.

Run: `python3 scripts/check_docs.py`

Expected: sin errores para el grupo.

- [ ] **Step 4: Crear checkpoint técnico**

```bash
git add docs/admin-console.md docs/ai-clients.md docs/chatgpt-gate.md docs/client-grants.md docs/controlled-write.md docs/gateway-mvp.md docs/lifecycle.md docs/mcp-adapter.md docs/os-migration.md docs/tunnel-client-provenance.md
git commit -m "docs: consolidate technical guides for v1.2.1"
```

---

### Task 7: Runbooks operativos seguros

**Files:**
- Modify: `docs/runbooks/admin-console.md`
- Modify: `docs/runbooks/claude-desktop.md`
- Modify: `docs/runbooks/controlled-write-smoke-test.md`
- Modify: `docs/runbooks/disaster-recovery.md`
- Modify: `docs/runbooks/doctor.md`
- Modify: `docs/runbooks/gateway-smoke-test.md`
- Modify: `docs/runbooks/gemini-cli.md`
- Modify: `docs/runbooks/mcp-smoke-test.md`
- Modify: `docs/runbooks/microsd-recovery.md`
- Modify: `docs/runbooks/network-recovery.md`
- Modify: `docs/runbooks/operations.md`
- Modify: `docs/runbooks/pi-to-pc-ssh.md`
- Modify: `docs/runbooks/reboot-recovery.md`
- Modify: `docs/runbooks/registry-backup-restore.md`
- Modify: `docs/runbooks/uninstall.md`
- Modify: `docs/runbooks/update-rollback.md`
- Modify: `docs/runbooks/write-recovery.md`

**Interfaces:**
- Consumes: manual canónico y comandos reales de CLI/systemd/scripts.
- Produces: procedimientos pequeños con prerrequisitos, evidencia, STOP y rollback explícitos.

- [ ] **Step 1: Auditar instrucciones peligrosas u obsoletas**

Run: `rg -n 'StrictHostKeyChecking=(no|accept-new)|file://|Yorologo|UID.?1001|r8188eu|192\.168\.68\.|v1\.0\.1|9/9|19/19' docs/runbooks`

Expected: coincidencias conocidas, incluida la configuración insegura de Gemini, que deben corregirse o contextualizarse.

- [ ] **Step 2: Normalizar formato operacional**

En cada runbook añadir: propósito, cuándo usarlo, prerrequisitos, pasos, evidencia esperada, STOP conditions y rollback/recovery. No duplicar instalación completa. Marcar como `OPCIONAL` Claude, Gemini, build Go, recuperación USB y rollback físico cuando no pertenezcan al camino mínimo.

- [ ] **Step 3: Corregir seguridad, identidad y plataforma**

Cambiar ejemplos a `StrictHostKeyChecking=yes` más `HostKeyAlias`/fingerprint; tratar IP como variable descubierta; usar `yorologo`; explicar `rtl8xxxu` en Trixie y `r8188eu` sólo como Bullseye histórico; no tocar Pi-hole. Sustituir conteos congelados de Doctor por criterios `HEALTHY` salvo que el conteo esté fechado como evidencia.

- [ ] **Step 4: Verificar comandos no destructivos y enlaces**

Run: `python3 scripts/check_docs.py`

Expected: `PASS: documentación consistente` o únicamente errores de archivos históricos aún pendientes.

Run: `rg -n 'StrictHostKeyChecking=(no|accept-new)|file://' docs/runbooks`

Expected: cero coincidencias.

- [ ] **Step 5: Crear checkpoint de runbooks**

```bash
git add docs/runbooks
git commit -m "docs: harden and align operational runbooks"
```

---

### Task 8: Contextualización de evidencia histórica

**Files:**
- Modify: `docs/releases/v1.0.1.md`
- Modify: `docs/releases/v1.1.0.md`
- Modify: `docs/releases/v1.1.1.md`
- Modify: `docs/releases/v1.2.0.md`
- Modify: `docs/releases/v1.2.1.md`
- Modify: `docs/inventory/baseline-2026-09-08.md`
- Modify: `docs/migration/pre-migration-inventory.md`
- Modify: `docs/v1-acceptance.md`

**Interfaces:**
- Consumes: Git history y contenido existente inmutable.
- Produces: cabeceras de contexto y enlaces al estado actual, sin alterar evidencia.

- [ ] **Step 1: Capturar hashes del contenido histórico antes de editar**

Run: `git show HEAD:docs/releases/v1.0.1.md | sha256sum && git show HEAD:docs/v1-acceptance.md | sha256sum`

Expected: hashes guardados en la salida de trabajo para comparar que el cuerpo histórico no se reescribió sustancialmente.

- [ ] **Step 2: Añadir una cabecera uniforme de contexto**

Después del título de cada archivo, añadir sólo:

```markdown
> **DOCUMENTO HISTÓRICO / EVIDENCIA.** Este archivo describe el baseline indicado en su título y no el estado operativo actual. Consultar [Estado actual](../../project-state.md) para el baseline vigente. Los endpoints aquí registrados son observaciones fechadas, no identidades.
```

Usar `../project-state.md` desde `docs/releases/`, `docs/inventory/` y `docs/migration/`; desde `docs/v1-acceptance.md`, usar `project-state.md`. En `v1.2.1.md`, usar `DOCUMENTO DE RELEASE VIGENTE` sin afirmar que cada endpoint observado sigue igual.

- [ ] **Step 3: Revisar el diff histórico línea por línea**

Run: `git diff --word-diff=porcelain -- docs/releases docs/inventory docs/migration docs/v1-acceptance.md`

Expected: cabeceras, enlaces y aclaraciones de contexto; sin cambios en checksums, fechas, resultados, fingerprints ni decisiones históricas.

- [ ] **Step 4: Ejecutar gate documental**

Run: `python3 scripts/check_docs.py`

Expected: `PASS: documentación consistente`.

- [ ] **Step 5: Crear checkpoint histórico**

```bash
git add docs/releases docs/inventory docs/migration docs/v1-acceptance.md
git commit -m "docs: label historical evidence without rewriting it"
```

---

### Task 9: Gate integral, revisión independiente y cierre

**Files:**
- Modify if required by verified findings: documentation files from Tasks 2–8
- Test: `tests/test_documentation.py`
- Verify only: frontend files already modified before this plan

**Interfaces:**
- Consumes: todos los checkpoints documentales y cambios frontend pendientes.
- Produces: evidencia reproducible para veredicto `PASS`, `PARTIAL` o `STOP`.

- [ ] **Step 1: Ejecutar validación documental y búsquedas negativas**

Run: `python3 -m unittest -v tests.test_documentation && python3 scripts/check_docs.py`

Expected: pruebas `OK` y `PASS: documentación consistente`.

Run: `rg -n 'StrictHostKeyChecking=(no|accept-new)|file://' README.md AGENTS.md docs scripts/check_docs.py`

Expected: cero instrucciones operativas inseguras; el propio patrón del comprobador puede aparecer y debe revisarse manualmente.

Run: `rg -n 'v1\.0\.1.*(actual|vigente|current)|catalog.*2|9 herramientas|9 tools' README.md AGENTS.md docs --glob '!docs/releases/**' --glob '!docs/inventory/**' --glob '!docs/migration/**' --glob '!docs/v1-acceptance.md'`

Expected: cero afirmaciones vigentes obsoletas.

- [ ] **Step 2: Validar el software Python**

Run: `python3 -m unittest discover -s tests -v`

Expected: suite completa `OK`; registrar cantidad real observada, sin copiar conteos históricos.

- [ ] **Step 3: Validar el adaptador Go con Registry aislado**

Crear una base temporal mediante las utilidades de prueba ya existentes, exportar `MCP_GATEWAY_DB` sólo para el proceso y ejecutar:

Run: `cd mcp-adapter && go test ./...`

Expected: `PASS`; si el test requiere clients/grants, sembrar únicamente el Registry temporal y documentar esa precondición.

- [ ] **Step 4: Verificar frontend pendiente sin mezclarlo en commits documentales**

Run: `node --test tests/test_app_js.mjs`

Expected: `PASS`.

Run: `cd tailwind && npm run build`

Expected: build `PASS`; una advertencia de `caniuse-lite` desactualizado no invalida el resultado.

- [ ] **Step 5: Ejecutar diff, Secret Gate y revisión histórica**

Run: `git diff --check && git status --short`

Expected: sin errores de whitespace; cambios frontend siguen identificables y separados.

Run: `git grep -nE -- '(BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|password\s*[:=]|token\s*[:=])' -- ':!docs/superpowers/**' ':!tests/**'`

Expected: cero secretos reales; revisar manualmente falsos positivos de ejemplos.

Run: `git diff 9b0d40e -- docs/releases docs/inventory docs/migration docs/v1-acceptance.md`

Expected: sólo contexto y enlaces, sin reescritura de evidencia.

- [ ] **Step 6: Solicitar revisión independiente**

Entregar al revisor: spec, plan, `compatibility.json`, diff completo y salidas de Steps 1–5. Pedir hallazgos priorizados sobre baseline, seguridad SSH, comandos destructivos, opcionales, enlaces, Mermaid, historia y cumplimiento de AGENTS. Corregir únicamente hallazgos demostrados y repetir el gate afectado.

- [ ] **Step 7: Crear checkpoint final documental**

Si la revisión exigió correcciones:

```bash
git add README.md AGENTS.md docs scripts/check_docs.py tests/test_documentation.py
git commit -m "docs: close v1.2.1 documentation review"
```

Si no hubo correcciones, no crear un commit vacío.

- [ ] **Step 8: Emitir veredicto con evidencia**

Declarar `PASS` sólo con todos los gates aplicables en verde. Declarar `PARTIAL` si queda una comprobación no ejecutable con su causa exacta. Declarar `STOP` ante contradicción de identidad, release, schema, listener público, secreto o pérdida de rollback.
