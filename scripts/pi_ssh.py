#!/usr/bin/env python3
import sys
import os
import time
import paramiko

def run_remote(cmd, as_user=None, timeout=180):
    host = os.environ.get("MCP_PI_HOST", "192.168.68.85")
    user = os.environ.get("MCP_PI_USER", "Yorologo")
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    
    full_cmd = f"sudo -u {as_user} {cmd}" if as_user else cmd
        
    for attempt in range(1, 9):
        ssh = paramiko.SSHClient()
        kh = os.path.expanduser("~/.ssh/mcp_known_hosts")
        if not os.path.isfile(kh):
            kh = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.isfile(kh):
            ssh.load_host_keys(kh)
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            ssh.connect(host, username=user, key_filename=key_path, timeout=20, banner_timeout=45)
            stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            ssh.close()
            return code, out, err
        except Exception as e:
            if attempt == 8:
                return -1, "", f"SSH failed after 8 attempts: {e}"
            time.sleep(attempt * 3.0)

def copy_to_remote(local_path, remote_path):
    host = os.environ.get("MCP_PI_HOST", "192.168.68.85")
    user = os.environ.get("MCP_PI_USER", "Yorologo")
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    
    for attempt in range(1, 9):
        ssh = paramiko.SSHClient()
        kh = os.path.expanduser("~/.ssh/mcp_known_hosts")
        if not os.path.isfile(kh):
            kh = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.isfile(kh):
            ssh.load_host_keys(kh)
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            ssh.connect(host, username=user, key_filename=key_path, timeout=20, banner_timeout=45)
            sftp = ssh.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            ssh.close()
            return True, "File uploaded successfully"
        except Exception as e:
            if attempt == 8:
                return False, f"SFTP failed after 8 attempts: {e}"
            time.sleep(attempt * 3.0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd = sys.stdin.read().strip()
    else:
        cmd = sys.argv[1]
    code, out, err = run_remote(cmd)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    sys.exit(code)
