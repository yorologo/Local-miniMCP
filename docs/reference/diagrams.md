# Architecture Diagrams

These diagrams describe the current production architecture, not historical phase snapshots.

## System architecture

```mermaid
flowchart LR
    U[User] --> C[ChatGPT / MCP client]
    C --> TUN[OpenAI Secure MCP Tunnel]
    TUN --> MCP[Go MCP Adapter\n127.0.0.1:8090]
    MCP --> B[Python Bridge]
    B --> CORE[Gateway Core / Policy]
    CORE --> REG[(SQLite Registry)]
    CORE --> SSH[SSH Transport]
    SSH --> TERM[termux-main\nAndroid / Termux]
    TERM --> PRJ[MCP_Local]
    WEB[Admin Browser\n192.168.68.55:80] --> ADMIN[Flask Admin Console]
    ADMIN --> REG
    ADMIN --> CORE
```

## Component boundaries

```mermaid
flowchart TB
    subgraph MCPPi[MCP-Pi / Raspberry Pi]
      ADMIN[Admin Console]
      ADAPTER[Go MCP Adapter]
      BRIDGE[Python Bridge]
      CORE[GatewayTools + Policy]
      REG[(Registry)]
      TRANS[SSH Transport]
      ADMIN --> CORE
      ADAPTER --> BRIDGE --> CORE
      CORE --> REG
      CORE --> TRANS
    end
    TRANS --> TARGET[Authorized Target]
    TARGET --> PROJECT[Authorized Project Root]
```

## MCP tool-call sequence

```mermaid
sequenceDiagram
    participant C as ChatGPT
    participant T as Secure Tunnel
    participant A as Go Adapter
    participant B as Python Bridge
    participant P as Policy/Core
    participant W as Target Worker
    C->>T: tools/call
    T->>A: MCP request
    A->>B: invoke(tool,args,client_id,request_id)
    B->>P: authorize + execute
    P->>P: grants / kill switches / project scope
    P->>W: SSH operation when required
    W-->>P: result
    P-->>B: structured response
    B-->>A: JSON result
    A-->>T: MCP response
    T-->>C: tool result
```

## Deployment topology

```mermaid
flowchart LR
    DEV[Termux development checkout] -->|run-resumable.sh + deploy-pi.sh / SSH| PI[MCP-Pi\n192.168.68.55]
    PI --> ADMIN[Admin Console\n:80 LAN]
    PI --> MCP[MCP Adapter\n:8090 loopback]
    MCP --> TUN[OpenAI Secure MCP Tunnel]
    PI -->|SSH :8022| PHONE[termux-main]
    PHONE --> REPO[MCP_Local]
```
