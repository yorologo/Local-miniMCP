# Runbook: Despliegue y Pruebas del Gateway Core en MCP-Pi

Este runbook documenta el procedimiento estándar para desplegar el código del Gateway Core en la Raspberry Pi `MCP-Pi` (`192.168.68.85`) y ejecutar la batería completa de verificación (pruebas unitarias remotas, pruebas en vivo contra targets y pruebas negativas de seguridad).

---

## 1. Requisitos Previos

- Conectividad SSH con `MCP-Pi` (`192.168.68.85:22`) como `Yorologo` (con contraseña o clave).
- Archivo de credenciales locales `.mcp-pi.local.env` presente y con permisos `600` en la raíz del repositorio.
- Configuración de targets locales en `config/targets.local.json`.
- Acceso SSH operativo desde la Raspberry Pi hacia el target `termux-main` (`192.168.68.84:8022`) vía usuario `mcp-gateway` (alias `pc-local` y `termux-local`).

---

## 2. Despliegue Automatizado y Pruebas Unitarias

El script `scripts/deploy-pi.sh` realiza las siguientes acciones:
1. Crea la estructura de directorios en `/home/mcp-gateway/mcp-gateway` con propiedad `mcp-gateway:mcp-gateway`.
2. Empaqueta y transfiere mediante un flujo tar comprimido los directorios `src/`, `config/targets.local.json` y `tests/`.
3. Ajusta permisos de forma que `mcp-gateway` sea el dueño exclusivo.
4. Ejecuta remotamente el descubridor de pruebas unitarias (`python3 -m unittest discover -s tests -p 'test_*.py' -v`) como usuario `mcp-gateway`.

### Ejecución:
```bash
./scripts/deploy-pi.sh
```

### Resultado esperado:
```text
=== Deploying MCP Gateway to MCP-Pi (192.168.68.85) ===
1. Creating remote directory structure...
2. Transferring files...
3. Running remote unit tests as mcp-gateway...
Ran 28 tests in 0.201s
OK
=== Deployment and remote tests completed successfully ===
```

---

## 3. Batería de Pruebas en Vivo y Negativas

Para verificar la integración real con el target `termux-main` y la efectividad de las políticas de seguridad deny-by-default, se utiliza el script:

```bash
./scripts/remote-smoke-test.sh
```

### Contenido de la Batería:
1. **Pruebas de Integración en Vivo**:
   - `health`: Comprueba estado local del gateway y versión de Python.
   - `list-targets`: Lista targets configurados y proyectos autorizados.
   - `target-status termux-main`: Mide latencia de red y verifica alcance del target.
   - `list-directory termux-main MCP_Local .`: Lista recursivamente el directorio raíz del proyecto.
   - `file-stat termux-main MCP_Local README.md`: Obtiene tamaño y timestamp de modificación.
   - `read-file termux-main MCP_Local README.md`: Lee el contenido del archivo con límite de 1 MiB.
   - `git-status termux-main MCP_Local`: Ejecuta `git status --short` de forma segura.
   - `run-task termux-main MCP_Local git_status`: Ejecuta la tarea predefinida en la lista blanca.

2. **Pruebas Negativas de Seguridad**:
   - Intento de escape traversal `../.bashrc` -> Denegado (`INVALID_PATH`).
   - Intento de ruta absoluta `/etc/passwd` -> Denegado (`INVALID_PATH`).
   - Intento de ejecución de tarea arbitraria `rm_rf` -> Denegado (`TASK_NOT_ALLOWED`).
   - Consulta de target inexistente `unknown-box` -> Denegado (`UNKNOWN_TARGET`).
   - Escape por symlink hacia `$HOME` fuera del root -> Denegado (`PATH_OUTSIDE_ALLOWED_ROOT`).

---

## 4. Invocación Manual Directa vía SSH

Para ejecutar un comando puntual desde la Raspberry Pi:

```bash
ssh Yorologo@192.168.68.85 "sudo -u mcp-gateway PYTHONPATH=/home/mcp-gateway/mcp-gateway/src python3 -m mcp_gateway.cli --config /home/mcp-gateway/mcp-gateway/config/targets.local.json <herramienta> [argumentos]"
```

Ejemplos:
```bash
# Diagnóstico de salud
... python3 -m mcp_gateway.cli health

# Estado del target
... python3 -m mcp_gateway.cli target-status termux-main

# Leer un archivo
... python3 -m mcp_gateway.cli read-file termux-main MCP_Local README.md
```
