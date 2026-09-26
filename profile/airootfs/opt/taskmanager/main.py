#!/usr/bin/env python3

import json
import os
import platform
import re
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

_rates = {
    "time": time.monotonic(),
    "disk_read": 0,
    "disk_write": 0,
    "net_rx": 0,
    "net_tx": 0,
}


def run_command(command, timeout=2):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def bytes_value(value):
    return int(value or 0)


def process_list():
    rows = []
    for proc in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent",
         "memory_info", "cmdline", "status"]
    ):
        try:
            info = proc.info
            memory = info.get("memory_info")
            rows.append({
                "pid": int(info["pid"]),
                "name": info.get("name") or "Unknown",
                "user": info.get("username") or "",
                "cpu": round(float(info.get("cpu_percent") or 0), 1),
                "mem": round(float(info.get("memory_percent") or 0), 1),
                "memRss": int(memory.rss // 1024) if memory else 0,
                "state": info.get("status") or "",
                "command": " ".join(info.get("cmdline") or []),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    rows.sort(key=lambda row: row["cpu"], reverse=True)
    return rows


def cpu_details(freq):
    brand = platform.processor() or ""
    manufacturer = ""
    vendor = ""
    family = ""
    model = ""

    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        text = cpuinfo.read_text(errors="replace")
        for line in text.splitlines():
            key, _, value = line.partition(":")
            value = value.strip()
            if key == "vendor_id" and not vendor:
                vendor = value
            elif key == "model name" and not brand:
                brand = value
            elif key == "cpu family" and not family:
                family = value
            elif key == "model" and not model:
                model = value

    if vendor.startswith("AuthenticAMD"):
        manufacturer = "AMD"
    elif vendor.startswith("GenuineIntel"):
        manufacturer = "Intel"
    elif vendor:
        manufacturer = vendor
    else:
        manufacturer = platform.system()

    caches = {}
    cache_root = Path("/sys/devices/system/cpu/cpu0/cache")
    if cache_root.exists():
        for item in cache_root.glob("index*"):
            try:
                level = (item / "level").read_text().strip()
                size = (item / "size").read_text().strip()
                if level == "1":
                    caches["l1"] = parse_size(size)
                elif level == "2":
                    caches["l2"] = parse_size(size)
                elif level == "3":
                    caches["l3"] = parse_size(size)
            except OSError:
                pass

    speed = (freq.current / 1000.0) if freq and freq.current else 0
    max_speed = (freq.max / 1000.0) if freq and freq.max else speed

    return {
        "manufacturer": manufacturer,
        "brand": brand or platform.machine(),
        "vendor": vendor or manufacturer,
        "family": family,
        "model": model,
        "speed": round(speed, 2),
        "speedMax": round(max_speed, 2),
        "physicalCores": psutil.cpu_count(logical=False) or 0,
        "cores": psutil.cpu_count(logical=True) or 0,
        "socket": "1",
        "cache": caches,
    }


def parse_size(value):
    match = re.match(r"([0-9.]+)\s*([KMG]?)", str(value).strip(), re.I)
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2).upper()
    multiplier = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}.get(unit, 1)
    return int(number * multiplier)


def memory_layout():
    modules = []
    output = run_command(
        ["dmidecode", "-t", "memory"], timeout=3
    ) if os.name != "nt" else ""

    if output:
        current = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Memory Device"):
                if current.get("size"):
                    modules.append(current)
                current = {}
            elif line.startswith("Size:"):
                value = line.split(":", 1)[1].strip()
                if value.lower() != "no module installed":
                    current["size"] = parse_size(value)
            elif line.startswith("Locator:"):
                current["bank"] = line.split(":", 1)[1].strip()
            elif line.startswith("Manufacturer:"):
                current["manufacturer"] = line.split(":", 1)[1].strip()
            elif line.startswith("Type:"):
                current["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("Speed:"):
                value = line.split(":", 1)[1].strip().split()[0]
                try:
                    current["clockSpeed"] = int(value)
                except ValueError:
                    pass
        if current.get("size"):
            modules.append(current)

    return modules


def physical_disks():
    disks = []
    output = run_command(
        ["lsblk", "-b", "-d", "-o", "NAME,SIZE,MODEL,VENDOR,TRAN,TYPE"],
        timeout=2,
    )
    if output:
        lines = output.splitlines()
        for line in lines[1:]:
            parts = line.split(None, 5)
            if len(parts) >= 2 and parts[-1] == "disk":
                name = parts[0]
                try:
                    size = int(parts[1])
                except ValueError:
                    size = 0
                disks.append({
                    "name": f"/dev/{name}",
                    "size": size,
                    "vendor": parts[3] if len(parts) > 3 else "",
                    "interfaceType": parts[4] if len(parts) > 4 else "",
                    "type": "disk",
                })
    return disks


def filesystem_info():
    result = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):
            continue
        result.append({
            "mount": part.mountpoint,
            "fs": part.fstype or "unknown",
            "type": part.device,
            "used": bytes_value(usage.used),
            "size": bytes_value(usage.total),
            "use": float(usage.percent),
        })
    return result


def network_info():
    stats = psutil.net_if_stats()
    addresses = psutil.net_if_addrs()
    per_iface = psutil.net_io_counters(pernic=True)

    interfaces = []
    for name, state in stats.items():
        addrs = addresses.get(name, [])
        mac = next(
            (a.address for a in addrs
             if getattr(a, "family", None) == getattr(psutil, "AF_LINK", None)),
            "",
        )
        ipv4 = next(
            (a.address for a in addrs
             if getattr(a, "family", None) == getattr(__import__("socket"), "AF_INET", None)),
            "",
        )
        ipv6 = next(
            (a.address for a in addrs
             if getattr(a, "family", None) == getattr(__import__("socket"), "AF_INET6", None)),
            "",
        )
        interfaces.append({
            "iface": name,
            "ifaceName": name,
            "internal": name.lower() in {"lo", "loopback"} or name.lower().startswith("lo"),
            "operstate": "up" if state.isup else "down",
            "speed": state.speed or 0,
            "mac": mac,
            "ip4": ipv4,
            "ip6": ipv6,
            "type": "network",
        })

    primary = None
    for item in interfaces:
        if not item["internal"] and item["operstate"] == "up":
            primary = item["iface"]
            break
    if primary is None and interfaces:
        primary = interfaces[0]["iface"]

    counter = per_iface.get(primary) if primary else None
    return interfaces, primary or "", counter


def system_info():
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    freq = psutil.cpu_freq()

    cpu_load = psutil.cpu_percent(interval=0.05)
    per_cpu = psutil.cpu_percent(interval=None, percpu=True)

    io = psutil.disk_io_counters()
    net = psutil.net_io_counters()
    now = time.monotonic()
    elapsed = max(now - _rates["time"], 0.001)

    read_bytes = bytes_value(getattr(io, "read_bytes", 0))
    write_bytes = bytes_value(getattr(io, "write_bytes", 0))
    rx_bytes = bytes_value(getattr(net, "bytes_recv", 0))
    tx_bytes = bytes_value(getattr(net, "bytes_sent", 0))

    read_rate = max(0, read_bytes - _rates["disk_read"]) / elapsed
    write_rate = max(0, write_bytes - _rates["disk_write"]) / elapsed
    rx_rate = max(0, rx_bytes - _rates["net_rx"]) / elapsed
    tx_rate = max(0, tx_bytes - _rates["net_tx"]) / elapsed

    _rates.update({
        "time": now,
        "disk_read": read_bytes,
        "disk_write": write_bytes,
        "net_rx": rx_bytes,
        "net_tx": tx_bytes,
    })

    interfaces, primary, primary_counter = network_info()
    primary_rx = bytes_value(getattr(primary_counter, "bytes_recv", 0))
    primary_tx = bytes_value(getattr(primary_counter, "bytes_sent", 0))

    filesystems = filesystem_info()
    disks = physical_disks()

    return {
        "cpu": {
            "currentLoad": float(cpu_load),
            "cpus": [{"load": float(load)} for load in per_cpu],
        },
        "cpuInfo": cpu_details(freq),
        "mem": {
            "total": bytes_value(vm.total),
            "active": bytes_value(vm.used),
            "available": bytes_value(vm.available),
            "buffcache": bytes_value(
                getattr(vm, "cached", 0) + getattr(vm, "buffers", 0)
            ),
            "swapused": bytes_value(swap.used),
            "swaptotal": bytes_value(swap.total),
        },
        "uptime": max(0, int(time.time() - psutil.boot_time())),
        "procCount": len(psutil.pids()),
        "memLayout": memory_layout(),
        "disks": filesystems,
        "diskLayout": disks,
        "disksIO": {
            "rIO_sec": read_rate,
            "wIO_sec": write_rate,
            "ms": elapsed * 1000,
        },
        "net": {
            "iface": primary,
            "rx_bytes": primary_rx or rx_bytes,
            "tx_bytes": primary_tx or tx_bytes,
            "rx_sec": rx_rate,
            "tx_sec": tx_rate,
        },
        "netIfaces": interfaces,
    }


def gpu_info():
    model = ""
    vendor = ""
    driver = ""
    vram_total = 0
    gfx = 0.0
    vram_used = 0.0
    mclk = 0.0
    sclk = 0.0

    if os.name == "nt":
        output = run_command(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | "
             "Select-Object -First 1 Name,AdapterRAM,DriverVersion | "
             "ConvertTo-Json -Compress"],
            timeout=3,
        )
        try:
            data = json.loads(output) if output else {}
            model = data.get("Name", "")
            driver = data.get("DriverVersion", "")
            vram_total = int(data.get("AdapterRAM") or 0)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    else:
        output = run_command(["lspci", "-nnk"], timeout=3)
        for line in output.splitlines():
            if "VGA compatible controller" in line or "3D controller" in line:
                model = line.split(":", 2)[-1].strip()
                break

        radeontop = run_command(
            ["radeontop", "-d", "-", "-l", "1"], timeout=2
        )
        if radeontop:
            def parse(pattern):
                match = re.search(pattern, radeontop)
                return float(match.group(1)) if match else 0.0

            gfx = parse(r"gpu\s+([\d.]+)%")
            vram_used = parse(r"vram\s+[\d.]+%\s+([\d.]+)mb")
            mclk = parse(r"mclk\s+[\d.]+%\s+([\d.]+)ghz")
            sclk = parse(r"sclk\s+[\d.]+%\s+([\d.]+)ghz")

        nvidia = run_command(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader,nounits"], timeout=2
        )
        if nvidia:
            parts = [x.strip() for x in nvidia.split(",", 3)]
            if len(parts) >= 4:
                model = parts[0]
                try:
                    vram_total = int(float(parts[1]) * 1024 * 1024)
                    vram_used = float(parts[2])
                except ValueError:
                    pass
                driver = parts[3]

    if model:
        lower = model.lower()
        if "amd" in lower or "radeon" in lower:
            vendor = "AMD"
        elif "nvidia" in lower or "geforce" in lower:
            vendor = "NVIDIA"
        elif "intel" in lower:
            vendor = "Intel"
        else:
            vendor = model.split(" ", 1)[0]

    return {
        "vendor": vendor or "Unknown",
        "model": model or "GPU information unavailable",
        "bus": None,
        "vramDetected": int(vram_total / (1024 * 1024)) if vram_total > 1024 * 1024 else vram_total,
        "driverVersion": driver,
        "gfx": gfx,
        "event": 0,
        "vgt": 0,
        "ta": 0,
        "sx": 0,
        "sci": 0,
        "si": 0,
        "sc": 0,
        "pa": 0,
        "db": 0,
        "cb": 0,
        "vramUsed": vram_used,
        "vramTotal": int(vram_total / (1024 * 1024)) if vram_total > 1024 * 1024 else 0,
        "mclk": mclk,
        "sclk": sclk,
    }


class APIHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
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
        self.send_json({})

    def do_GET(self):
        if self.path == "/api/system":
            self.send_json(system_info())
        elif self.path == "/api/processes":
            self.send_json({"list": process_list()})
        elif self.path == "/api/gpu":
            self.send_json(gpu_info())
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path != "/api/kill":
            self.send_json({"error": "Not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            pid = int(payload["pid"])
            if pid <= 0 or pid == os.getpid():
                raise ValueError("Invalid PID")

            proc = psutil.Process(pid)
            proc.kill()
            self.send_json({"success": True})
        except (KeyError, ValueError, psutil.NoSuchProcess):
            self.send_json({"success": False, "error": "Process not found"}, 404)
        except psutil.AccessDenied:
            self.send_json({"success": False, "error": "Access denied"}, 403)
        except Exception as exc:
            self.send_json({"success": False, "error": str(exc)}, 500)

    def log_message(self, *_):
        return


def start_api_server():
    server = ThreadingHTTPServer((API_HOST, API_PORT), APIHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Manager")
        self.resize(1200, 800)
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
