# Architecture

MCP-Pi is a small security gateway, not a compute platform. The appliance centralizes identity, policy, audit and protocol adaptation; Targets perform the actual work.

## Components

```mermaid
flowchart LR
    C[AI / MCP client] --> A[Go MCP adapter]
    B[Admin browser] --> W[Flask Admin Console]
    A --> G[Gateway Core]
    W --> G
    G --> P[Policy engine]
    P --> R[(SQLite Registry)]
    G --> S[SSH transport]
    S --> T[Target]
    T --> PR[Authorized Project]
```

The Admin Console and MCP adapter **must use the same Gateway Core**. There is no parallel Admin-to-SSH bypass.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| Go MCP adapter | MCP protocol, HTTP/stdin transport, client identity handoff, tool annotations |
| Gateway Core | canonical tool behavior, limits, audit and orchestration |
| Policy | client/grant/Target/Project/capability authorization |
| Registry | Targets, Projects, clients, grants, settings and activity |
| SSH transport | pinned Target connection and bounded remote operations |
| Admin Console | human configuration using the same Registry/Core |
| Target | performs project work; not trusted merely because its IP matches |

## Request flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as MCP adapter
    participant G as Gateway Core
    participant P as Policy / Registry
    participant S as SSH transport
    participant T as Target

    C->>A: tools/list or tools/call
    A->>G: authenticated client + request
    G->>P: authorize capability/scope
    alt denied
        P-->>G: deny
        G-->>A: structured fail-closed error
        A-->>C: denied
    else allowed
        P-->>G: allow
        G->>S: bounded operation
        S->>T: pinned SSH session
        T-->>S: result
        S-->>G: result
        G->>P: audit result
        G-->>A: structured result
        A-->>C: MCP response
    end
```

## Tool families

The catalog currently contains 21 deterministic tools. They fall into four practical groups:

- read/introspection;
- structured project filesystem mutations;
- allowlisted project tasks;
- appliance administration plus trusted Target shell.

Structured filesystem mutations enforce Project-root canonical paths. `run_command` is different: it is a **trusted Target shell** for explicitly authorized clients. Its Project identifies authorization scope and initial working directory; it is not a filesystem sandbox.

## Identity versus endpoint

A Target ID and pinned SSH host key establish identity. DHCP addresses and ports are runtime endpoints and may change.

```text
Target ID + SSH host fingerprint = identity
IP + port                         = endpoint
```

Endpoint rediscovery may update an address only after cryptographic identity matches. An unexpected host key fails closed.

## Runtime layout

```text
/home/mcp-gateway/mcp-gateway/                  application runtime
/home/mcp-gateway/.local/share/mcp-gateway/    Registry + backups
/home/mcp-gateway/.config/mcp-gateway/          private config + secrets
/etc/systemd/system/                             service definitions
```

Application updates must not overwrite persistent Registry/config/secrets.

## Installation and deployment boundaries

```mermaid
flowchart TD
    U[User release bundle] --> I[install.sh]
    I --> R[Installed runtime]
    M[Maintainer exact Git SHA] --> D[scripts/deploy-pi.sh]
    D --> C[Validated candidate]
    C --> R
    R --> P[Persistent data/config]
```

`install.sh` is the user install/reinstall path. `deploy-pi.sh` is a maintainer promotion mechanism with exact-commit provenance and transactional rollback.

## Resource model

The reference appliance is intentionally constrained. Heavy tests, frontend builds and Go cross-compilation run on a development host. The appliance runs only lightweight validation/Doctor and the production services.

See [security.md](security.md), [configuration.md](configuration.md) and [compatibility.md](reference/compatibility.md).
