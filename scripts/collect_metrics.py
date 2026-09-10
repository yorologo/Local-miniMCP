#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.pi_ssh import run_remote

def main():
    commands = [
        ("MEMINFO", "grep -E 'MemTotal|MemFree|MemAvailable' /proc/meminfo"),
        ("ZRAM", "/sbin/zramctl --noheadings --output NAME,DISKSIZE,DATA,COMPR,ALGORITHM"),
        ("TEMP", "vcgencmd measure_temp"),
        ("THROTTLED", "vcgencmd get_throttled"),
        ("UPTIME", "uptime"),
        ("PROCESSES", "ps -o pid,user,vsz,rss,comm -p 5297,5298"),
        ("OOM_COUNT", "dmesg | grep -ic oom || true"),
        ("USB_DISCONNECTS", "dmesg | grep -icE 'disconnect|reset high-speed USB device' || true"),
        ("WLAN0_STATS", "cat /proc/net/dev | grep wlan0"),
        ("LISTENERS", "ss -tulpn | grep -E '8080|8090|22'"),
        ("WRITES_ENABLED", "python3 -c \"import sys; sys.path.insert(0, '/home/mcp-gateway/mcp-gateway/src'); from mcp_gateway.registry import get_registry; print(get_registry().get_setting('writes_enabled'))\""),
        ("GIT_STATUS", "cd /home/mcp-gateway/mcp-gateway && git status --short && git diff --stat")
    ]

    for title, cmd in commands:
        code, out, err = run_remote(cmd, as_user="mcp-gateway")
        print(f"=== {title} ===")
        print(out.strip() if out.strip() else err.strip())
        print()

if __name__ == "__main__":
    main()
