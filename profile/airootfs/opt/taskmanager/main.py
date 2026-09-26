#!/usr/bin/env python3
import os
import signal
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

def meminfo():
    d = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        d[k] = int(v.split()[0]) * 1024
    total = d.get("MemTotal", 0)
    free = d.get("MemAvailable", d.get("MemFree", 0))
    return total - free, total

def cpuinfo():
    v = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:]))
    return sum(v), v[3] + v[4]

def netinfo():
    rx = tx = 0
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        if ":" not in line:
            continue
        iface, data = line.split(":", 1)
        if iface.strip() == "lo":
            continue
        f = data.split()
        if len(f) >= 9:
            rx += int(f[0]); tx += int(f[8])
    return rx, tx

def processes():
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            text = (p / "stat").read_text()
            end = text.rfind(")")
            name = text[text.find("(")+1:end]
            fields = text[end+2:].split()
            rss = int(fields[21]) * os.sysconf("SC_PAGE_SIZE")
            out.append((int(p.name), name, fields[0], rss))
        except (OSError, ValueError, IndexError):
            pass
    return sorted(out, key=lambda x: x[3], reverse=True)

def size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

class Card(QLabel):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("Card")
        self.setText(f"{title}\n—")
        self.title = title
    def set_value(self, value):
        self.setText(f"{self.title}\n{value}")

class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MuliOS Task Manager")
        self.resize(1050, 700)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18,18,18,18)

        head = QHBoxLayout()
        title = QLabel("MuliOS Task Manager")
        title.setObjectName("Title")
        head.addWidget(title)
        head.addStretch()
        self.status = QLabel("Monitoring")
        self.status.setObjectName("Muted")
        head.addWidget(self.status)
        layout.addLayout(head)

        self.tabs = QTabWidget()
        self.overview = QWidget()
        ov = QVBoxLayout(self.overview)
        row = QHBoxLayout()
        self.cpu = Card("CPU")
        self.mem = Card("Memory")
        self.disk = Card("Disk")
        self.net = Card("Network")
        for x in (self.cpu,self.mem,self.disk,self.net):
            row.addWidget(x)
        ov.addLayout(row)
        self.detail = QLabel("Live system statistics")
        self.detail.setObjectName("Muted")
        ov.addWidget(self.detail)
        ov.addStretch()

        self.table = QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(["PID","Process","State","Memory"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.disk_page = QLabel()
        self.disk_page.setObjectName("Value")
        self.net_page = QLabel()
        self.net_page.setObjectName("Value")
        about = QLabel("MuliOS Task Manager\nNative PySide6 implementation.\nNo Electron runtime.")
        about.setObjectName("Value")

        self.tabs.addTab(self.overview, "Overview")
        self.tabs.addTab(self.table, "Processes")
        self.tabs.addTab(self.disk_page, "Disk")
        self.tabs.addTab(self.net_page, "Network")
        self.tabs.addTab(about, "About")
        layout.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        kill = QPushButton("End process")
        kill.clicked.connect(self.kill_process)
        actions.addWidget(kill)
        layout.addLayout(actions)

        self.old_cpu = cpuinfo()
        self.old_net = netinfo()
        self.old_time = time.monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self):
        try:
            now = time.monotonic()
            total, idle = cpuinfo()
            ot, oi = self.old_cpu
            dt = max(1, total-ot)
            cpu = max(0, min(100, 100*(1-(idle-oi)/dt)))
            self.old_cpu = total, idle

            used, total_mem = meminfo()
            st = os.statvfs("/")
            total_disk = st.f_blocks * st.f_frsize
            free_disk = st.f_bavail * st.f_frsize
            used_disk = total_disk-free_disk

            rx, tx = netinfo()
            orx, otx = self.old_net
            elapsed = max(.1, now-self.old_time)
            rr, tr = max(0,(rx-orx)/elapsed), max(0,(tx-otx)/elapsed)
            self.old_net, self.old_time = (rx,tx), now

            self.cpu.set_value(f"{cpu:.0f}%")
            self.mem.set_value(f"{size(used)} / {size(total_mem)}")
            self.disk.set_value(f"{size(used_disk)} / {size(total_disk)}")
            self.net.set_value(f"↓ {size(rr)}/s  ↑ {size(tr)}/s")
            self.disk_page.setText(f"Root filesystem\n\nUsed: {size(used_disk)}\nFree: {size(free_disk)}\nTotal: {size(total_disk)}")
            self.net_page.setText(f"Network\n\nDownload: {size(rr)}/s\nUpload: {size(tr)}/s")

            ps = processes()
            self.table.setRowCount(len(ps))
            for r,(pid,name,state,rss) in enumerate(ps):
                for c,v in enumerate((pid,name,state,size(rss))):
                    self.table.setItem(r,c,QTableWidgetItem(str(v)))
            self.status.setText(f"Monitoring · {len(ps)} processes")
        except Exception as e:
            self.status.setText(f"Monitoring error: {e}")

    def kill_process(self):
        r = self.table.currentRow()
        if r < 0:
            return
        pid = int(self.table.item(r,0).text())
        if pid <= 1:
            return
        if QMessageBox.question(self,"End process",f"Terminate PID {pid}?") != QMessageBox.Yes:
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            QMessageBox.warning(self,"Unable to terminate process",str(e))

def main():
    app = QApplication([])
    app.setStyleSheet("""
        QWidget { background: transparent; color: #f3f5f7; font-family: Inter, Cantarell, sans-serif; }
        #Root { background: #111318; border: 1px solid rgba(255,255,255,35); border-radius: 14px; }
        #Title { font-size: 18pt; font-weight: 650; }
        #Muted { color: #a9afb8; }
        #Value { font-size: 16pt; padding: 20px; }
        #Card { background: rgba(31,35,43,225); border: 1px solid rgba(255,255,255,35); border-radius: 12px; padding: 14px; font-size: 14pt; }
        QTabWidget::pane { background: rgba(31,35,43,225); border: 1px solid rgba(255,255,255,35); border-radius: 12px; }
        QTabBar::tab { background: transparent; color: #a9afb8; padding: 9px 16px; }
        QTabBar::tab:selected { color: #f3f5f7; border-bottom: 2px solid #319cc8; }
        QPushButton { background: rgba(40,45,55,230); color: #f3f5f7; border: 1px solid rgba(255,255,255,35); border-radius: 9px; padding: 8px 16px; }
        QPushButton:hover { border-color: #319cc8; }
        QTableWidget { background: rgba(17,19,24,215); border: 0; gridline-color: rgba(255,255,255,25); }
        QHeaderView::section { background: rgba(40,45,55,230); color: #a9afb8; border: 0; padding: 8px; }
    """)
    w = TaskManager()
    w.show()
    app.exec()

if __name__ == "__main__":
    main()
