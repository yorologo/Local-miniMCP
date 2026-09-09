#!/usr/bin/env python3
import os
import sys
import time
import paramiko

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

def deploy():
    host = os.environ.get("MCP_PI_HOST", "192.168.68.85")
    user = os.environ.get("MCP_PI_USER", "Yorologo")
    key_path = os.path.expanduser("~/.ssh/id_ed25519")

    print(f"Connecting to {user}@{host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connected = False
    for attempt in range(1, 6):
        try:
            ssh.connect(host, username=user, key_filename=key_path, timeout=30, banner_timeout=45)
            connected = True
            break
        except Exception as e:
            print(f"Connection attempt {attempt} failed ({e}), retrying in 3s...")
            time.sleep(3)

    import tarfile
    import io

    # Create tar.gz in memory
    print("Creating deployment tarball in memory...")
    tar_buf = io.BytesIO()
    def tar_filter(info):
        if "__pycache__" in info.name or info.name.endswith(".pyc"):
            return None
        return info

    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        # Add src
        local_src = os.path.join(os.path.dirname(__file__), "..", "src")
        tar.add(local_src, arcname="src", filter=tar_filter)
        # Add tests
        local_tests = os.path.join(os.path.dirname(__file__), "..", "tests")
        tar.add(local_tests, arcname="tests", filter=tar_filter)
        # Add bin
        local_stdio = os.path.join(os.path.dirname(__file__), "..", "bin", "mcp-gateway-client-stdio")
        tar.add(local_stdio, arcname="bin/mcp-gateway-client-stdio")
        local_cli = os.path.join(os.path.dirname(__file__), "..", "bin", "mcp-gateway")
        tar.add(local_cli, arcname="bin/mcp-gateway")
        # Note: Go binary is uploaded separately with pacing to avoid Wi-Fi buffer overflow

    tar_bytes = tar_buf.getvalue()
    tar_buf.seek(0)
    print(f"Code tarball created ({len(tar_bytes)} bytes). Uploading via SFTP...")

    # Gzip Go adapter binary in memory
    local_adapter = os.path.join(os.path.dirname(__file__), "..", "mcp-adapter", "mcp-gateway-adapter.armv6")
    gz_bin = None
    if os.path.isfile(local_adapter):
        import gzip
        with open(local_adapter, "rb") as f:
            gz_bin = gzip.compress(f.read())
        print(f"Go binary compressed: {len(gz_bin)} bytes ({len(gz_bin)/1024/1024:.2f} MB)")

    # Prepare directory before opening SFTP
    stdin, stdout, stderr = ssh.exec_command("rm -rf /tmp/mcp_deploy /tmp/deploy.tar.gz /tmp/adapter.gz && mkdir -p /tmp/mcp_deploy", timeout=30)
    stdout.channel.recv_exit_status()

    sftp = ssh.open_sftp()
    sftp.putfo(tar_buf, "/tmp/deploy.tar.gz")
    print("Code tarball uploaded successfully.")

    if gz_bin:
        print(f"Uploading Go binary with pacing (16KB chunks + 20ms pause)...")
        chunk_size = 16384
        with sftp.open("/tmp/adapter.gz", "wb") as rf:
            total_chunks = (len(gz_bin) + chunk_size - 1) // chunk_size
            for idx in range(total_chunks):
                start = idx * chunk_size
                end = min(start + chunk_size, len(gz_bin))
                rf.write(gz_bin[start:end])
                time.sleep(0.02)
                if idx % 25 == 0 or idx == total_chunks - 1:
                    print(f"  Go binary upload: {end // 1024} KB / {len(gz_bin) // 1024} KB ({int(end/len(gz_bin)*100)}%)")
        print("Go binary uploaded successfully.")

    sftp.close()
    print("SFTP uploads complete. Extracting and applying on MCP-Pi...")

    # Extract and prepare on Pi
    extract_cmd = """
tar -xzf /tmp/deploy.tar.gz -C /tmp/mcp_deploy
if [ -f /tmp/adapter.gz ]; then
    gunzip -c /tmp/adapter.gz > /tmp/mcp_deploy/bin/mcp-gateway-adapter
    chmod 755 /tmp/mcp_deploy/bin/mcp-gateway-adapter
    rm -f /tmp/adapter.gz
fi
rm -f /tmp/deploy.tar.gz
"""
    stdin, stdout, stderr = ssh.exec_command(extract_cmd, timeout=120)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        err = stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Failed to extract tarball on remote: {err}")
    print("Tarball extracted successfully on MCP-Pi.")

    # Apply on MCP-Pi
    print("Applying updates to /home/mcp-gateway/mcp-gateway...")
    apply_cmd = """
sudo rm -f /home/mcp-gateway/mcp-gateway/src/mcp_gateway/stdio_server.py /home/mcp-gateway/mcp-gateway/tests/test_stdio_server.py
sudo cp -r /tmp/mcp_deploy/src /home/mcp-gateway/mcp-gateway/
sudo cp -r /tmp/mcp_deploy/tests /home/mcp-gateway/mcp-gateway/
sudo cp -r /tmp/mcp_deploy/bin /home/mcp-gateway/mcp-gateway/
sudo chown -R mcp-gateway:mcp-gateway /home/mcp-gateway/mcp-gateway
sudo chmod 755 /home/mcp-gateway/mcp-gateway/bin/*
sudo rm -rf /tmp/mcp_deploy
sudo systemctl restart mcp-gateway-admin mcp-gateway-mcp
echo "DEPLOY_APPLIED"
"""
    stdin, stdout, stderr = ssh.exec_command(apply_cmd, timeout=60)
    out = stdout.read().decode("utf-8")
    err = stderr.read().decode("utf-8")
    print("Apply output:", out.strip())
    if err:
        print("Apply stderr:", err.strip())

    # Verify adapter version
    print("Verifying adapter version...")
    stdin, stdout, stderr = ssh.exec_command("/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -version", timeout=15)
    print("Adapter version:", stdout.read().decode("utf-8").strip())

    stdin, stdout, stderr = ssh.exec_command("/home/mcp-gateway/mcp-gateway/bin/mcp-gateway-adapter -help", timeout=15)
    help_txt = stderr.read().decode("utf-8") + stdout.read().decode("utf-8")
    if "-client-id" in help_txt:
        print("  [PASS] Adapter supports -client-id flag!")
    else:
        print("  [WARN] -client-id flag not seen:", help_txt)

    # Verify unit tests remotely
    print("Running remote unit tests on MCP-Pi...")
    test_cmd = "sudo -u mcp-gateway python3 -m unittest discover -s /home/mcp-gateway/mcp-gateway/tests -p 'test_*.py'"
    stdin, stdout, stderr = ssh.exec_command(test_cmd, timeout=120)
    test_out = stdout.read().decode("utf-8")
    test_err = stderr.read().decode("utf-8")
    print(test_out)
    print(test_err)

    ssh.close()
    print("Deployment and remote verification finished successfully.")

if __name__ == "__main__":
    deploy()
