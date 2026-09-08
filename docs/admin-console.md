# MCP Gateway - Consola de Administración Segura

La **Consola de Administración** de MCP Gateway proporciona una interfaz web ligera, segura y centralizada para administrar targets, proyectos, clientes de IA y configuraciones operacionales, montada sobre la Raspberry Pi Model A+ (`MCP-Pi`).

---

## 1. Arquitectura de Acceso

Por diseño estricto de seguridad, la consola web **NO** está expuesta a la red local (LAN) ni a Internet.

```text
  [ Navegador del Administrador ]
                │
                │ Conexión segura SSH (Túnel local)
                ▼
       ssh -L 8080:127.0.0.1:8080
                │
                ▼
  [ Raspberry Pi (MCP-Pi) ]
  127.0.0.1:8080 (Loopback exclusivo)
                │
         ┌──────┴──────┐
         │ Flask Admin │
         │   Console   │ (Python 3.9 + Jinja2 + Tailwind CSS)
         └──────┬──────┘
                │
         ┌──────┴──────┐
         │  Registry   │ (SQLite 3.34 - Parameterized Queries)
         └──────┬──────┘
                │
         ┌──────┴──────┐
         │ GatewayCore │ (Validación de políticas y allowlist)
         └──────┬──────┘
                │
                ▼  (SSH con clave Ed25519)
         [ Target Worker ]
```

---

## 2. Principios de Seguridad Implementados

1. **Binding Exclusivo a Localhost (`127.0.0.1:8080`)**:
   - Imposible acceder directamente a través de la IP de la LAN (`192.168.68.85:8080`).
   - Requiere autenticación SSH administrativa con la Raspberry Pi previa apertura de túnel.

2. **Ejecución Bajo Cuenta Sin Privilegios (`mcp-gateway`)**:
   - Se ejecuta bajo el usuario de servicio `mcp-gateway` (UID 1001), sin privilegios `sudo`.
   - Servicio systemd aislado con `NoNewPrivileges=true` y `PrivateTmp=true`.

3. **Protección de Sesión y Autenticación**:
   - Cookies de sesión con atributos `HttpOnly` y `SameSite=Strict`.
   - Hashes de contraseñas mediante PBKDF2-SHA256 con salt aleatorio (Werkzeug).
   - Regeneración de identificador de sesión tras autenticación exitosa (mitigación de fijación de sesión).
   - Expiración automática de sesión (30 minutos por defecto).
   - Rate limiting contra fuerza bruta: 5 intentos fallidos en 5 minutos activan un bloqueo temporal de 60 segundos por usuario.

4. **Cabeceras de Seguridad HTTP (Middleware Global)**:
   - `Content-Security-Policy`: Restringe scripts y estilos a `'self'`, bloquea embebido en frames (`frame-ancestors 'none'`).
   - `X-Content-Type-Options: nosniff`: Previene MIME sniffing.
   - `X-Frame-Options: DENY`: Protección absoluta contra clickjacking.
   - `Referrer-Policy: no-referrer`: Previene fuga de URLs en cabeceras HTTP.
   - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`: Previene almacenamiento de vistas administrativas en caché del navegador.

5. **Protección CSRF (Cross-Site Request Forgery)**:
   - Tokens únicos generados criptográficamente por sesión (`os.urandom(32).hex()`).
   - Validación obligatoria mediante `hmac.compare_digest` en todas las rutas POST/mutaciones.
   - Denegación automática de mutaciones ejecutadas mediante peticiones GET.

6. **Defensa en Profundidad en Base de Datos**:
   - 100% de consultas SQL parametrizadas (`?`), previniendo inyecciones SQL.
   - Motor SQLite stdlib puro sin ORMs pesados.

---

## 3. Funcionalidades Principales

### Dashboard (`/dashboard`)
- Estado en tiempo real del Gateway (`ok` / `disabled`).
- Contadores de targets activos/totales, proyectos y clientes de IA registrados.
- Métricas del sistema en vivo: memoria RAM disponible, carga promedio de CPU, tamaño de base de datos.
- Resumen de las últimas 5 actividades registradas en el log de auditoría.

### Gestión de Targets (`/targets`)
- Listado detallado de targets con plataforma, host, puerto, usuario y alias SSH.
- Creación y edición de targets.
- **Acción Test**: Verificación de conectividad en vivo invocando `GatewayTools.target_status` a través del núcleo del Gateway (nunca SSH directo desde Flask).
- **Toggle Enable/Disable**: Deshabilita un target individual de inmediato. Si un target está deshabilitado, cualquier petición de herramienta MCP retorna error `TARGET_DISABLED`.

### Gestión de Proyectos (`/projects`)
- Listado de proyectos asociados a sus respectivos targets.
- Configuración de ruta raíz autorizada (`root`), permisos de lectura (`read`) y escritura (`write`).
- Lista de tareas predefinidas en lista blanca con sus argumentos `argv` y límites de tiempo (`timeout`).
- Habilitación y deshabilitación individual de proyectos (`PROJECT_DISABLED`).

### Clientes de IA (`/clients`)
- Registro de clientes o agentes autorizados (nombre, proveedor, protocolo y notas).
- Habilitación/deshabilitación de clientes para control de acceso centralizado.

### Registro de Actividad y Auditoría (`/activity`)
- Registro cronológico detallado de operaciones realizadas por el gateway.
- Visualización de actor, acción, target, proyecto, duración en milisegundos, estado (`OK` / `ERROR`) y códigos de error estandarizados.
- Paginación integrada y botón de purga según la política de retención configurada.

### Diagnóstico del Sistema (`/system`)
- Información del host: Hostname (`MCP-Pi`), IP local, modelo de hardware (`Raspberry Pi Model A+`), arquitectura de CPU (`armv6l`), sistema operativo y versión de kernel.
- Entorno de ejecución: Versión de Python, versión del Gateway (`0.2.0`), backend de registro activo (`SQLiteRegistry`), ruta y tamaño de la base de datos.
- Estadísticas de recursos: Uptime, memoria física total/usada/libre, partición de disco y swap.

### Configuración y Kill Switch Global (`/settings`)
- Parámetros operacionales: `default_timeout`, `max_output_bytes`, `max_file_read_bytes`, `activity_retention`.
- **Interruptor de Emergencia Global (Emergency Kill Switch)**:
  - Permite desactivar inmediatamente la orquestación (`gateway_enabled = false`).
  - Cuando está activo, toda petición de herramientas dirigidas a targets (`list_directory`, `read_file`, `git_status`, `run_task`, `target_status`) es rechazada con el código `GATEWAY_DISABLED`.
  - La herramienta `health` y la Consola Web continúan operativas para permitir supervisión y reactivación.

---

## 4. Consumo de Recursos en Raspberry Pi Model A+

Mediciones en vivo ejecutadas en `MCP-Pi` (ARMv6 single-core 700MHz, 176 MiB RAM):
- **Memoria de Proceso (RSS)**: ~19.0 MiB (28,332 KB VSZ, 19,480 KB RSS).
- **Memoria Libre del Sistema**: ~82 MiB libres / ~89 MiB disponibles de 176 MiB totales.
- **Tamaño de Base de Datos SQLite**: 64 KB inicial.
- **Latencia HTTP (Localhost)**: ~50 ms por petición en caliente (~1.29 s en arranque en frío por carga de librerías).
- **Hoja de Estilos Tailwind CSS**: 17,323 bytes precompilados (cero dependencias de Node.js en la Raspberry Pi).
