#!/usr/bin/env python3
import gzip
import os
import subprocess
import sys
import tarfile
import time


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    host = "192.168.68.85"
    user = "Yorologo"
    key = os.path.expanduser("~/.ssh/id_ed25519")

    print("=== Deploying MCP-Pi Gateway v1.0.1 to MCP-Pi ===")

    # 1. Prepare tarball
    bundle_path = os.path.join(root, "deploy_bundle_v101.tar.gz")
    print(f"1. Creating {bundle_path}...")

    def tar_filter(info):
        if "__pycache__" in info.name or info.name.endswith(".pyc"):
            return None
        return info

    with tarfile.open(bundle_path, mode="w:gz") as tar:
        tar.add(os.path.join(root, "src"), arcname="src", filter=tar_filter)
        tar.add(os.path.join(root, "tests"), arcname="tests", filter=tar_filter)
        tar.add(os.path.join(root, "manifest.json"), arcname="manifest.json")
        tar.add(os.path.join(root, "compatibility.json"), arcname="compatibility.json")
        tar.add(os.path.join(root, "SHA256SUMS"), arcname="SHA256SUMS")
        tar.add(os.path.join(root, "install.sh"), arcname="install.sh")
        tar.add(os.path.join(root, "bin", "mcp-gateway"), arcname="bin/mcp-gateway")
        tar.add(os.path.join(root, "bin", "mcp-gateway-client-stdio"), arcname="bin/mcp-gateway-client-stdio")
        tar.add(os.path.join(root, "config", "targets.example.json"), arcname="config/targets.example.json")

    bundle_size = os.path.getsize(bundle_path)
    print(f"Bundle created: {bundle_size} bytes")

    # 2. Compress ARMv6 binary
    armv6_bin = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter-linux-armv6")
    armv6_gz = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter-v101.armv6.gz")
    print(f"2. Compressing ARMv6 Go binary ({armv6_bin})...")
    with open(armv6_bin, "rb") as f_in, gzip.open(armv6_gz, "wb") as f_out:
        f_out.write(f_in.read())
    print(f"Adapter compressed: {os.path.getsize(armv6_gz)} bytes")

    # 3. SCP transfer bundle
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

    time.sleep(1.0)

    # 4. SCP transfer adapter binary
    print("4. Transferring Go adapter binary via scp -O (-l 600)...")
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

    # 5. Remote install
    print("5. Installing bundle and adapter on MCP-Pi...")
    remote_script = """set -e
sudo tar -xzf /tmp/deploy_bundle_v101.tar.gz -C /home/mcp-gateway/mcp-gateway
gunzip -c /tmp/mcp-gateway-adapter-v101.armv6.gz > /tmp/mcp-gateway-adapter
sudo mv /tmp/mcp-gateway-adapter /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/mcp-gateway
sudo chmod 755 /home/mcp-gateway/mcp-gateway/bin/*
rm -f /tmp/deploy_bundle_v101.tar.gz /tmp/mcp-gateway-adapter-v101.armv6.gz
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
echo "DEPLOY_V101_OK"
"""
    ssh_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        remote_script
    ]
    res = subprocess.run(ssh_cmd, capture_output=True, text=True)
    print("Install output:\n", res.stdout)
    if res.returncode != 0:
        print("Install error:\n", res.stderr)
        sys.exit(res.returncode)

    # 6. Verify version
    print("6. Verifying adapter version...")
    v_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        "/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -version"
    ]
    res = subprocess.run(v_cmd, capture_output=True, text=True)
    print("Version output:", res.stdout.strip())
    assert "v1.0.1" in res.stdout, f"Expected v1.0.1 in output, got: {res.stdout}"

    # 7. Cleanup local tmp files
    if os.path.exists(bundle_path):
        os.remove(bundle_path)
    if os.path.exists(armv6_gz):
        os.remove(armv6_gz)

    print("\n=== DEPLOYMENT V1.0.1 COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
