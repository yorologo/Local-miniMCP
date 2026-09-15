#!/usr/bin/env python3
import gzip
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pi_ssh


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    print("=== Deploying Appliance Tools Update to MCP-Pi ===")

    # 1. Prepare tarball
    bundle_path = os.path.join(root, "deploy_bundle_appliance.tar.gz")
    print(f"1. Creating {bundle_path}...")

    def tar_filter(info):
        if "__pycache__" in info.name or info.name.endswith(".pyc"):
            return None
        return info

    with tarfile.open(bundle_path, mode="w:gz") as tar:
        tar.add(os.path.join(root, "src"), arcname="src", filter=tar_filter)
        tar.add(os.path.join(root, "tests"), arcname="tests", filter=tar_filter)
        if os.path.isfile(os.path.join(root, "compatibility.json")):
            tar.add(os.path.join(root, "compatibility.json"), arcname="compatibility.json")

    bundle_size = os.path.getsize(bundle_path)
    print(f"Bundle created: {bundle_size} bytes")

    # 2. Compress ARMv6 binary
    armv6_bin = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter-linux-armv6")
    armv6_gz = os.path.join(root, "mcp-adapter", "mcp-gateway-adapter-appliance.armv6.gz")
    print(f"2. Compressing ARMv6 Go binary ({armv6_bin})...")
    with open(armv6_bin, "rb") as f_in, gzip.open(armv6_gz, "wb") as f_out:
        f_out.write(f_in.read())
    print(f"Adapter compressed: {os.path.getsize(armv6_gz)} bytes")

    # 3. Transfer bundle via pi_ssh SFTP
    print("3. Transferring bundle via SFTP...")
    ok, msg = pi_ssh.copy_to_remote(bundle_path, "/tmp/deploy_bundle_appliance.tar.gz")
    if not ok:
        print("SFTP bundle transfer failed:", msg)
        sys.exit(1)
    print("Bundle transferred successfully.")

    # 4. Transfer adapter binary via pi_ssh SFTP
    print("4. Transferring Go adapter binary via SFTP...")
    ok, msg = pi_ssh.copy_to_remote(armv6_gz, "/tmp/mcp-gateway-adapter-appliance.armv6.gz")
    if not ok:
        print("SFTP adapter transfer failed:", msg)
        sys.exit(1)
    print("Adapter transferred successfully.")

    # 5. Remote install
    print("5. Installing bundle and adapter on MCP-Pi...")
    install_script = """set -e
sudo tar -xzf /tmp/deploy_bundle_appliance.tar.gz -C /home/mcp-gateway/mcp-gateway
gunzip -c /tmp/mcp-gateway-adapter-appliance.armv6.gz > /tmp/mcp-gateway-adapter
sudo mv /tmp/mcp-gateway-adapter /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/mcp-gateway
sudo chmod 755 /home/mcp-gateway/mcp-gateway/bin/*
rm -f /tmp/deploy_bundle_appliance.tar.gz /tmp/mcp-gateway-adapter-appliance.armv6.gz
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
echo "DEPLOY_APPLIANCE_OK"
"""
    code, out, err = pi_ssh.run_remote(install_script)
    print("Install output:\n", out)
    if code != 0:
        print("Install error:\n", err)
        sys.exit(code)

    # 6. Verify services
    print("6. Verifying services and version...")
    code, out, err = pi_ssh.run_remote("systemctl is-active mcp-gateway-admin mcp-gateway-mcp && /home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -version")
    print("Verification output:\n", out.strip())

    # 7. Cleanup local tmp files
    if os.path.exists(bundle_path):
        os.remove(bundle_path)
    if os.path.exists(armv6_gz):
        os.remove(armv6_gz)

    print("\n=== DEPLOYMENT COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
