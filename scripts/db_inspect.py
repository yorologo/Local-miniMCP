import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

cmd = """sudo -u mcp-gateway python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src')
from mcp_gateway.registry import get_registry
r = get_registry()
print('TARGETS:', r.list_targets())
for t in r.list_targets():
    tid = t['id']
    print(f'PROJECTS for {tid}:', r.list_projects(tid))
print('CLIENTS:', r.list_clients())
print('GRANTS:', r.list_grants())
EOF
"""
code, out, err = run_remote(cmd)
print(out)
if err:
    print("ERR:", err)
