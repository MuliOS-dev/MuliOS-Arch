#!/usr/bin/env python3

import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView


BASE_DIR = Path(__file__).resolve().parent
HTML = BASE_DIR / "index.html"
API_HOST = "127.0.0.1"
API_PORT = 4700


def bytes_value(value):
    return int(value or 0)


def process_list():
    rows = []
    for proc in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent", "memory_info", "cmdline"]
    ):
        try:
            info = proc.info
            memory = info.get("memory_info")
            rows.append({
                "pid": int(info["pid"]),
                "name": info.get("name") or "Unknown",
                "user": info.get("username") or "",
                "cpu": float(info.get("cpu_percent") or 0),
                "mem": float(info.get("memory_percent") or 0),
                "memRss": int(memory.rss // 1024) if memory else 0,
                "command": " ".join(info.get("cmdline") or []),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    rows.sort(key=lambda row: row["cpu"], reverse=True)
    return rows


def system_info():
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_freq = psutil.cpu_freq()

    partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):
            continue

        partitions.append({
            "mount": part.mountpoint,
            "fs": part.fstype or "unknown",
            "type": part.device,
            "used": bytes_value(usage.used),
            "size": bytes_value(usage.total),
            "use": float(usage.percent),
        })

    io = psutil.disk_io_counters()
    net = psutil.net_io_counters()
    interfaces = psutil.net_if_stats()
    addresses = psutil.net_if_addrs()

    primary_iface = ""
    primary_rx = primary_tx = 0
    if net:
        primary_iface = next(iter(addresses), "")
        if primary_iface:
            per_iface = psutil.net_io_counters(pernic=True).get(primary_iface)
            if per_iface:
                primary_rx = per_iface.bytes_recv
                primary_tx = per_iface.bytes_sent

    net_ifaces = []
    for name, stats in interfaces.items():
        addrs = addresses.get(name, [])
        ip4 = next(
            (a.address for a in addrs if a.family == getattr(psutil, "AF_LINK", object())),
            "",
        )
        ipv4 = next(
            (a.address for a in addrs if str(a.family).endswith("AF_INET")),
            "",
        )
        ipv6 = next(
            (a.address for a in addrs if str(a.family).endswith("AF_INET6")),
            "",
        )
        net_ifaces.append({
            "iface": name,
            "ifaceName": name,
            "internal": name.lower().startswith(("lo", "loopback")),
            "operstate": stats.isup and "up" or "down",
            "speed": stats.speed or 0,
            "mac": ip4,
            "ip4": ipv4,
            "ip6": ipv6,
            "type": "network",
        })

    cpu_name = platform.processor() or platform.machine() or "Unknown CPU"
    cpu_speed = (cpu_freq.current / 1000.0) if cpu_freq and cpu_freq.current else 0
    cpu_max = (cpu_freq.max / 1000.0) if cpu_freq and cpu_freq.max else cpu_speed

    return {
        "cpu": {
            "currentLoad": float(psutil.cpu_percent(None)),
            "cpus": [{"load": load} for load in psutil.cpu_percent(None, percpu=True)],
        },
        "cpuInfo": {
            "manufacturer": platform.system(),
            "brand": cpu_name,
            "vendor": platform.machine(),
            "family": "",
            "model": "",
            "speed": round(cpu_speed, 2),
            "speedMax": round(cpu_max, 2),
            "physicalCores": psutil.cpu_count(logical=False) or 0,
            "cores": psutil.cpu_count(logical=True) or 0,
            "socket": "1",
            "cache": {},
        },
        "mem": {
            "total": bytes_value(vm.total),
            "active": bytes_value(vm.used),
            "available": bytes_value(vm.available),
            "buffcache": bytes_value(getattr(vm, "cached", 0) + getattr(vm, "buffers", 0)),
            "swapused": bytes_value(swap.used),
            "swaptotal": bytes_value(swap.total),
        },
        "uptime": max(0, int(time.time() - psutil.boot_time())),
        "procCount": len(psutil.pids()),
        "memLayout": [],
        "disks": partitions,
        "diskLayout": partitions,
        "disksIO": {
            "rIO_sec": bytes_value(getattr(io, "read_bytes", 0)),
            "wIO_sec": bytes_value(getattr(io, "write_bytes", 0)),
        },
        "net": {
            "iface": primary_iface,
            "rx_bytes": bytes_value(primary_rx),
            "tx_bytes": bytes_value(primary_tx),
            "rx_sec": 0,
            "tx_sec": 0,
        },
        "netIfaces": net_ifaces,
    }


def gpu_info():
    model = ""
    vendor = ""

    if os.name == "nt":
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Select-Object -First 1 -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            model = result.stdout.strip()
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in result.stdout.splitlines():
                if "VGA compatible controller" in line or "3D controller" in line:
                    model = line.split(":", 2)[-1].strip()
                    break
        except Exception:
            pass

    if model:
        vendor = model.split(" ", 1)[0]

    return {
        "model": model or "GPU information unavailable",
        "vendor": vendor,
        "gfx": 0,
        "vramUsed": 0,
        "vramTotal": 0,
        "vramDetected": 0,
        "mclk": 0,
        "sclk": 0,
        "driverVersion": "",
    }


class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        if self.path == "/api/system":
            self._send_json(system_info())
        elif self.path == "/api/gpu":
            self._send_json(gpu_info())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path != "/api/kill":
            self._send_json({"error": "Not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            pid = int(payload["pid"])
            if pid <= 0 or pid == os.getpid():
                raise ValueError("Invalid process")
            proc = psutil.Process(pid)
            proc.terminate()
            self._send_json({"success": True})
        except (KeyError, ValueError, psutil.NoSuchProcess):
            self._send_json({"success": False, "error": "Process not found"}, 404)
        except psutil.AccessDenied:
            self._send_json({"success": False, "error": "Access denied"}, 403)
        except Exception as exc:
            self._send_json({"success": False, "error": str(exc)}, 500)

    def log_message(self, format, *args):
        return


def start_api_server():
    server = ThreadingHTTPServer((API_HOST, API_PORT), APIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MuliOS Task Manager")
        self.resize(1200, 760)

        self.server = start_api_server()

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl.fromLocalFile(str(HTML)))
        self.setCentralWidget(self.browser)

    def closeEvent(self, event):
        self.server.shutdown()
        self.server.server_close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = TaskManager()
    window.show()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
