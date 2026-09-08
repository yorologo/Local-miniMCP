# Arquitectura MCP Raspberry Pi Gateway

## 1. Visión Conceptual

El objetivo del proyecto es establecer un Gateway MCP personal en una Raspberry Pi Model A+ que actúe como perímetro de seguridad, intermediario y orquestador entre ChatGPT y la estación de trabajo principal (PC).

```text
+-------------------+
|      ChatGPT      |
+-------------------+
          |
          | MCP Seguro (Model Context Protocol)
          v
+-------------------+
|  Raspberry Pi A+  |  --> [Frontera de seguridad / Orquestador / Gateway Core]
|  (192.168.68.85)  |      Valida, autoriza, limita, orquesta, audita (Python stdlib)
+-------------------+
          |
          | SSH / SFTP (Controlado y restringido vía clave exclusiva Ed25519)
          v
+-------------------+
|   PC Principal    |  --> [Nodo de cómputo y almacenamiento pesado]
|                   |      Almacena, busca, compila, ejecuta, procesa
+-------------------+
```

---

## 2. Roles y Separación de Responsabilidades

### Raspberry Pi Model A+ (Gateway)
- **Frontera de seguridad**: Expone únicamente interfaces controladas y autorizadas hacia el cliente/agente LLM.
- **Orquestación y auditoría**: Registra las operaciones solicitadas, valida políticas de acceso y supervisa el tráfico.
- **Bajo consumo y aislamiento**: No ejecuta modelos LLM ni tareas pesadas de compilación o análisis intensivo de datos, adecuándose a sus recursos (CPU ARMv6 single-core, ~176 MB RAM utilizables).
- **Deny-by-default**: Todas las operaciones no explícitamente permitidas están denegadas.
- **Zero-External-Dependencies**: El núcleo opera al 100% sobre la librería estándar de Python 3, evitando sobrecarga en ARMv6 y protegiendo el sistema operativo Raspbian 11 de dependencias pesadas.

### PC Principal (Worker / Storage)
- **Cómputo pesado**: Ejecución de compilaciones, indexación de archivos grandes, ejecución de pruebas pesadas o contenedores.
- **Almacenamiento**: Persistencia principal de repositorios y proyectos.
- **Acceso controlado**: Recibe únicamente comandos u operaciones canalizadas a través del canal SSH auditado desde el Gateway.

---

## 3. Topología de Red y Dispositivos Relevantes

| Dispositivo / Rol | Dirección IP | Hostname | Interfaz Activa | Estado en el Proyecto |
|---|---|---|---|---|
| **Raspberry Pi Gateway** | `192.168.68.85` | `MCP-Pi` | `wlan0` (Wi-Fi USB RTL8188EUS) | **Objetivo activo del gateway** |
| **Raspberry Pi (Pi-hole)** | `192.168.68.54` | `YorPi` | N/A | **FUERA DEL ALCANCE** (Dispositivo crítico LAN; no tocar) |
| **Gateway LAN (Router)** | `192.168.68.1` | - | LAN | Router / Servidor DHCP local |
| **Target Primario (Worker)** | `192.168.68.84:8022` | `localhost` | Wi-Fi LAN | Target `termux-main` (Android 16 / Termux) |

> [!CAUTION]
> **Aislamiento de Pi-hole (`192.168.68.54`)**:
> La Raspberry Pi con IP `192.168.68.54` actúa como DNS/Pi-hole de la red local y conserva su hostname `YorPi`. Está totalmente fuera del alcance de este proyecto y NO debe ser modificada, reiniciada ni alterada por ningún agente.

> [!NOTE]
> **Colisión de Hostname Resuelta**:
> La colisión inicial fue resuelta en la Fase 2A renombrando la Raspberry del gateway a `MCP-Pi`. La Raspberry Pi-hole conserva su nombre `YorPi`. No existe conflicto de resolución local.

---

## 4. Arquitectura del Gateway Core (Fase 4A)

El Gateway Core reside en `/home/mcp-gateway/mcp-gateway` en la Raspberry Pi y está desacoplado del protocolo final y de la plataforma subyacente.

```text
[ Cliente / Interfaz / Adaptador de Protocolo ]
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│                      GATEWAY CORE                      │
│                                                        │
│  ┌──────────────────┐        ┌──────────────────────┐  │
│  │  GatewayConfig   │ ◄────► │    Policy Engine     │  │
│  │ (config/targets) │        │ (Deny-by-default)    │  │
│  └──────────────────┘        └──────────────────────┘  │
│                                          │             │
│  ┌──────────────────┐                    │             │
│  │   GatewayTools   │ ───────────────────┘             │
│  │  (8 herramientas)│                                  │
│  └──────────────────┘                                  │
│            │                                           │
│            ▼                                           │
│  ┌──────────────────┐                                  │
│  │   SSHTransport   │                                  │
│  │ (OpenSSH stdlib) │                                  │
│  └──────────────────┘                                  │
└────────────┬───────────────────────────────────────────┘
             │
             │ Conexión SSH segura vía alias OpenSSH
             ▼
[ Target Remoto: Linux / macOS / Windows / Android-Termux ]
```

### 4.1 Capas del Núcleo
1. **Configuración (`config.py`)**:
   - Soporte nativo para múltiples targets y múltiples proyectos por target.
   - Declaración de raíces autorizadas (`root`), capacidades permitidas (`read`, `tasks`, etc.) y tareas predefinidas en lista blanca con vectores `argv` estrictos.
2. **Motor de Políticas (`policy.py`)**:
   - **Sintaxis de rutas**: Rechazo de rutas absolutas, traversals (`..`), caracteres nulos y paths vacíos.
   - **Validación canónica remota**: Resolución con `realpath` en el target para garantizar que la ruta resuelta habite dentro del `root` del proyecto, previniendo escapes mediante enlaces simbólicos o colisiones de prefijos hermanos.
   - **Lista blanca de tareas**: Solo se pueden ejecutar comandos explícitamente declarados en la configuración.
3. **Transporte SSH (`ssh_transport.py`)**:
   - Invocación de `ssh` mediante `subprocess` estándar sin shells intermedios (`shell=False`).
   - Comillas seguras con `shlex.quote`.
   - Lector seguro de archivos de texto (límite de 1 MiB, aborto si se detectan bytes nulos binarios).
4. **Herramientas de Alto Nivel (`tools.py`)**:
   - Implementa: `health`, `list_targets`, `target_status`, `list_directory`, `file_stat`, `read_file`, `git_status`, `run_task`.
   - Respuestas uniformes en JSON con estado (`ok`), herramienta (`tool`), duración (`duration_ms`), resultado estructurado (`result`) o error estandarizado (`error`).

---

## 5. Implementación del Canal Seguro Pi → Target

```text
[ MCP-Pi Gateway ]                               [ PC Principal / Worker ]
(192.168.68.85)                                  (192.168.68.84)
Usuario: mcp-gateway (UID 1001, sin sudo)        Usuario: u0_a435 (App Android / Termux, sin root)
Clave: ~/.ssh/mcp_gateway_ed25519                Puerto: 8022
Alias: pc-local / termux-local                   Allowed Root: .../MCP_Local
        |                                                ^
        +================== SSH =========================+
                    (Ed25519 sin password)
```

- **Separación de privilegios en el Gateway**: El canal hacia el target se ejecuta exclusivamente desde la cuenta de servicio `mcp-gateway`, sin acceso a `sudo` ni credenciales administrativas de la Raspberry.
- **Entorno del Worker en PC**: Ejecutado en un sandbox Linux/Android sin privilegios de root (`u:r:untrusted_app_27`), con OpenSSH Server en el puerto 8022.
- **Alcance acotado**: Delimitado al root del proyecto para impedir modificaciones o lecturas imprevistas fuera del espacio asignado.

---

## 6. Registro Persistente y Consola de Administración (Fase 4B)

La Fase 4B introduce una capa de persistencia transaccional y una consola de gestión web protegida que se sitúa sobre el Gateway Core sin alterar sus garantías de seguridad:

```text
       [ Administrador ]
               │
               │ Túnel SSH (ssh -L 8080:127.0.0.1:8080)
               ▼
┌────────────────────────────────────────────────────────┐
│ MCP-Pi (127.0.0.1:8080)                                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Consola Web Admin (Flask + Jinja2)          │  │
│  │     - Estilos Tailwind CSS precompilados         │  │
│  │     - CSRF, HttpOnly, SameSite=Strict, CSP       │  │
│  │     - PBKDF2 password hash, Rate limiting        │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Registry Abstraction Layer             │  │
│  │                                                  │  │
│  │   ┌────────────────────┐   ┌─────────────────┐   │  │
│  │   │   SQLiteRegistry   │   │  JsonRegistry   │   │  │
│  │   │  (gateway.db 64K)  │   │   (Fallback)    │   │  │
│  │   └────────────────────┘   └─────────────────┘   │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │             Gateway Core (tools.py)              │  │
│  │  - Emergency Kill Switch (gateway_enabled)       │  │
│  │  - Target / Project Enable / Disable check       │  │
│  │  - Deny-by-default Policy Engine                 │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │                          │
│                             ▼                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           SSHTransport (Subprocess)              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────┬──────────────────────────┘
                              │
                              │ SSH Ed25519
                              ▼
                       [ Target Worker ]
```

### 6.1 Capa de Registro Abstraída
- **`RegistryBase` (ABC)**: Interfaz uniforme para operaciones de consulta y mutación.
- **`SQLiteRegistry`**: Almacén principal en `/home/mcp-gateway/.local/share/mcp-gateway/gateway.db`. Consultas 100% parametrizadas (`?`), control de versión de esquema con `PRAGMA user_version = 1`.
- **`JsonRegistry`**: Adaptador compatible hacia atrás para `config/targets.local.json`.
- **Rollback transparente**: La variable de entorno `MCP_GATEWAY_REGISTRY=json|sqlite` permite alternar de backend instantáneamente sin cambios de código.

### 6.2 Consola Web de Administración
- **Aislamiento de Red**: Escucha estrictamente en `127.0.0.1:8080`, inaccesible directamente por la LAN (`192.168.68.85`).
- **Zero Node.js en Raspberry Pi**: El CSS de Tailwind (17 KB) se compila en el entorno de desarrollo y se despliega como activo estático estricto.
- **Operaciones Core Auditas**: La consola invoca `GatewayTools` para pruebas y diagnósticos; nunca ejecuta comandos SSH arbitrarios desde los controladores web.
- **Interruptor de Emergencia (Emergency Kill Switch)**: Corta globalmente el acceso de las herramientas a los targets en milisegundos actualizando `gateway_enabled = false` en la base de datos.

