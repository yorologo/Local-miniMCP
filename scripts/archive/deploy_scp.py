#!/usr/bin/env python3
import os
import sys
import subprocess
import gzip
import tarfile

def deploy():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    host = "192.168.68.85"
    user = "Yorologo"
    key = os.path.expanduser("~/.ssh/id_ed25519")

    print("=== Deploying Phase 6A Closeout to MCP-Pi via scp -O ===")

    # 1. Prepare tarball
    print("1. Creating deploy_bundle.tar.gz...")
    bundle_path = os.path.join(root, "deploy_bundle.tar.gz")
    def tar_filter(info):
        if "__pycache__" in info.name or info.name.endswith(".pyc"):
            return None
        return info

    with tarfile.open(bundle_path, mode="w:gz") as tar:
        tar.add(os.path.join(root, "src"), arcname="src", filter=tar_filter)
        tar.add(os.path.join(root, "tests"), arcname="tests", filter=tar_filter)
        tar.add(os.path.join(root, "bin", "mcp-gateway-client-stdio"), arcname="bin/mcp-gateway-client-stdio")
        tar.add(os.path.join(root, "bin", "mcp-gateway"), arcname="bin/mcp-gateway")
    print(f"Bundle created: {os.path.getsize(bundle_path)} bytes")

    # 2. Compress Go binary
    armv6_bin = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter.armv6")
    armv6_gz = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter.armv6.gz")
    print("2. Compressing ARMv6 Go binary...")
    with open(armv6_bin, "rb") as f_in, gzip.open(armv6_gz, "wb") as f_out:
        f_out.write(f_in.read())
    print(f"Adapter compressed: {os.path.getsize(armv6_gz)} bytes")

    # 3. SCP transfer using legacy SCP (-O) and safe bandwidth limit (-l 600 ~ 75KB/s)
    print("3. Transferring bundle via scp -O (-l 600)...")
    scp_bundle = [
        "scp", "-O", "-l", "600",
        "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        bundle_path,
        f"{user}@{host}:/tmp/"
    ]
    res = subprocess.run(scp_bundle, capture_output=True, text=True)
    if res.returncode != 0:
        print("SCP bundle failed:", res.stderr)
        sys.exit(res.returncode)
    print("Bundle transferred successfully.")

    import time
    time.sleep(1.0)

    print("Transferring Go adapter binary via scp -O (-l 600)...")
    scp_bin = [
        "scp", "-O", "-l", "600",
        "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        armv6_gz,
        f"{user}@{host}:/tmp/"
    ]
    res = subprocess.run(scp_bin, capture_output=True, text=True)
    if res.returncode != 0:
        print("SCP adapter failed:", res.stderr)
        sys.exit(res.returncode)
    print("Adapter transferred successfully.")

    # 4. Install and configure on MCP-Pi
    print("4. Installing bundle and adapter on MCP-Pi...")
    remote_script = """set -e
sudo rm -f /home/mcp-gateway/mcp-gateway/src/mcp_gateway/stdio_server.py /home/mcp-gateway/mcp-gateway/tests/test_stdio_server.py
sudo tar -xzf /tmp/deploy_bundle.tar.gz -C /home/mcp-gateway/mcp-gateway
gunzip -c /tmp/mcp-gateway-adapter.armv6.gz > /tmp/mcp-gateway-adapter
sudo mv /tmp/mcp-gateway-adapter /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/mcp-gateway
sudo chmod 755 /home/mcp-gateway/mcp-gateway/bin/*
rm -f /tmp/deploy_bundle.tar.gz /tmp/mcp-gateway-adapter.armv6.gz
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
echo "INSTALL_OK"
"""
    ssh_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        remote_script
    ]
    res = subprocess.run(ssh_cmd, capture_output=True, text=True)
    print("Install output:\n", res.stdout)
    if res.stderr:
        print("Install stderr:\n", res.stderr)
    if res.returncode != 0:
        sys.exit(res.returncode)

    # 5. Verify adapter version & help
    print("5. Verifying adapter version and flags...")
    verify_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        "/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -version; /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -help"
    ]
    res = subprocess.run(verify_cmd, capture_output=True, text=True)
    print(res.stdout)
    if "-client-id" in (res.stderr + res.stdout):
        print("  [PASS] Adapter supports -client-id flag!")
    else:
        print("  [FAIL] Adapter missing -client-id flag!")
        sys.exit(1)

    # 6. Run remote Python tests
    print("6. Running remote Python unit tests on MCP-Pi...")
    test_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        "sudo -u mcp-gateway python3 -m unittest discover -s /home/mcp-gateway/mcp-gateway/tests -p 'test_*.py'"
    ]
    res = subprocess.run(test_cmd, capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    if res.returncode != 0:
        print("Remote unit tests failed!")
        sys.exit(res.returncode)

    # 7. Cleanup local tmp files
    if os.path.exists(bundle_path):
        os.remove(bundle_path)
    if os.path.exists(armv6_gz):
        os.remove(armv6_gz)

    print("\n=== DEPLOYMENT AND VERIFICATION FINISHED SUCCESSFULLY ===")

if __name__ == "__main__":
    deploy()
