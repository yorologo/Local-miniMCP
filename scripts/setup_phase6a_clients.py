import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

gemini_pub = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFC7lFYzxlLBDTFTxx1yCnJ4s4ht219Ve8WxEXI7xwvo mcp-client:gemini-main"
claude_pub = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0UEb1SEcfYqCvt7xQRuhfvRqKmegU8GQXocY//QOHu mcp-client:claude-desktop"

setup_script = f"""sudo -u mcp-gateway python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src')
from mcp_gateway.registry import get_registry

r = get_registry()

# 1. Register clients
clients = [
    {{"id": "gemini-main", "name": "Gemini CLI Main Client", "client_type": "cli", "enabled": True}},
    {{"id": "claude-desktop", "name": "Claude Desktop Client", "client_type": "desktop", "enabled": True}}
]

for c in clients:
    try:
        r.add_client(c)
        print(f"Added client: {{c['id']}}")
    except Exception as e:
        r.update_client(c["id"], c)
        print(f"Updated client: {{c['id']}}")

# 2. Add initial grants
# gemini-main: read,execute on * (all 8 read/control tools, NO write_file)
r.add_grant({{
    "id": "grant-gemini-read-exec",
    "client_id": "gemini-main",
    "target_id": "*",
    "project_id": "*",
    "capability": "read,execute",
    "enabled": True
}})
print("Added grant-gemini-read-exec")

# claude-desktop: read on * (read tools only)
r.add_grant({{
    "id": "grant-claude-read",
    "client_id": "claude-desktop",
    "target_id": "*",
    "project_id": "*",
    "capability": "read",
    "enabled": True
}})
print("Added grant-claude-read")

print("CLIENTS:", r.list_clients())
print("GRANTS:", r.list_grants())
EOF
"""

print("Registering clients and grants in SQLite...")
code, out, err = run_remote(setup_script)
print(out)
if err:
    print("ERR:", err)
if code != 0:
    sys.exit(code)

# 3. Setup authorized_keys on MCP-Pi for mcp-gateway user
auth_keys_cmd = f"""sudo -u mcp-gateway bash -c '
mkdir -p /home/mcp-gateway/.ssh
chmod 700 /home/mcp-gateway/.ssh
cat > /home/mcp-gateway/.ssh/authorized_keys << "KEYS"
command="/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio gemini-main",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty {gemini_pub}
command="/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-client-stdio claude-desktop",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty {claude_pub}
KEYS
chmod 600 /home/mcp-gateway/.ssh/authorized_keys
ls -la /home/mcp-gateway/.ssh/authorized_keys
'"""

print("Setting up authorized_keys for mcp-gateway...")
code, out, err = run_remote(auth_keys_cmd)
print(out)
if err:
    print("ERR:", err)
if code != 0:
    sys.exit(code)

print("Setup completed successfully.")
