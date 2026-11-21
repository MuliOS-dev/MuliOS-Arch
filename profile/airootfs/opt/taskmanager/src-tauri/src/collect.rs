//! System metrics collection (replaces `systeminformation` + `radeontop` glue from main.js).

use std::collections::HashMap;
use std::fs;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use shared::*;
use sysinfo::{Components, Disks, Networks, Pid, ProcessesToUpdate, System, Users};

/// (sectors read, sectors written, ms spent doing I/O)
type IoCounters = (u64, u64, u64);

struct DriveStatic {
    name: String,
    model: String,
    kind: String,
    size: u64,
}

pub struct Collector {
    sys: System,
    psys: System,
    users: Users,
    disks: Disks,
    networks: Networks,
    components: Components,
    drives: Vec<DriveStatic>,
    prev_io: HashMap<String, IoCounters>,
    last_io: Instant,
    last_net: Instant,
    hostname: String,
    os: String,
}

fn read_trim(path: &str) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_string())
}

fn read_diskstats() -> HashMap<String, IoCounters> {
    let mut map = HashMap::new();
    if let Ok(text) = fs::read_to_string("/proc/diskstats") {
        for line in text.lines() {
            let f: Vec<&str> = line.split_whitespace().collect();
            if f.len() < 13 {
                continue;
            }
            let p = |i: usize| f[i].parse::<u64>().unwrap_or(0);
            map.insert(f[2].to_string(), (p(5), p(9), p(12)));
        }
    }
    map
}

fn list_drives() -> Vec<DriveStatic> {
    let mut out = Vec::new();
    let Ok(rd) = fs::read_dir("/sys/block") else {
        return out;
    };
    for entry in rd.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        if ["loop", "ram", "zram", "dm-", "sr", "md"]
            .iter()
            .any(|p| name.starts_with(p))
        {
            continue;
        }
        let base = format!("/sys/block/{name}");
        let size = read_trim(&format!("{base}/size"))
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(0)
            * 512;
        if size == 0 {
            continue;
        }
        let model = read_trim(&format!("{base}/device/model")).unwrap_or_default();
        let kind = if name.starts_with("nvme") {
            "NVMe"
        } else if read_trim(&format!("{base}/queue/rotational")).as_deref() == Some("1") {
            "HDD"
        } else {
            "SSD"
        }
        .to_string();
        out.push(DriveStatic { name, model, kind, size });
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

fn count_processes() -> usize {
    fs::read_dir("/proc")
        .map(|rd| {
            rd.flatten()
                .filter(|e| e.file_name().to_string_lossy().bytes().all(|b| b.is_ascii_digit()))
                .count()
        })
        .unwrap_or(0)
}

impl Collector {
    pub fn new() -> Self {
        let mut sys = System::new();
        sys.refresh_cpu_all();
        sys.refresh_memory();
        let mut psys = System::new();
        psys.refresh_processes(ProcessesToUpdate::All, true);
        Self {
            sys,
            psys,
            users: Users::new_with_refreshed_list(),
            disks: Disks::new_with_refreshed_list(),
            networks: Networks::new_with_refreshed_list(),
            components: Components::new_with_refreshed_list(),
            drives: list_drives(),
            prev_io: read_diskstats(),
            last_io: Instant::now(),
            last_net: Instant::now(),
            hostname: System::host_name().unwrap_or_default(),
            os: System::long_os_version().unwrap_or_else(|| "Linux".into()),
        }
    }

    pub fn snapshot(&mut self) -> SystemSnapshot {
        self.sys.refresh_cpu_all();
        self.sys.refresh_memory();
        self.disks.refresh(true);
        self.components.refresh(true);

        // ---- CPU
        let cpus = self.sys.cpus();
        let cpu = CpuInfo {
            brand: cpus.first().map(|c| c.brand().trim().to_string()).unwrap_or_default(),
            vendor: cpus.first().map(|c| c.vendor_id().to_string()).unwrap_or_default(),
            physical_cores: self.sys.physical_core_count().unwrap_or(0),
            logical_cores: cpus.len(),
            speed_mhz: if cpus.is_empty() {
                0
            } else {
                cpus.iter().map(|c| c.frequency()).sum::<u64>() / cpus.len() as u64
            },
            load: self.sys.global_cpu_usage(),
            per_core: cpus.iter().map(|c| c.cpu_usage()).collect(),
        };

        // ---- Memory
        let total = self.sys.total_memory();
        let available = self.sys.available_memory();
        let mem = MemInfo {
            total,
            used: total.saturating_sub(available),
            available,
            swap_total: self.sys.total_swap(),
            swap_used: self.sys.used_swap(),
        };

        // ---- Filesystems
        const SKIP_FS: [&str; 6] = ["tmpfs", "devtmpfs", "squashfs", "overlay", "efivarfs", "ramfs"];
        let filesystems = self
            .disks
            .list()
            .iter()
            .filter(|d| {
                let fs = d.file_system().to_string_lossy();
                d.total_space() > 0 && !SKIP_FS.contains(&fs.as_ref())
            })
            .map(|d| {
                let size = d.total_space();
                let used = size.saturating_sub(d.available_space());
                FsInfo {
                    mount: d.mount_point().to_string_lossy().to_string(),
                    fs: d.file_system().to_string_lossy().to_string(),
                    kind: format!("{:?}", d.kind()),
                    size,
                    used,
                    use_pct: if size > 0 { used as f32 / size as f32 * 100.0 } else { 0.0 },
                }
            })
            .collect();

        // ---- Physical drives (real I/O from /proc/diskstats)
        let dt = self.last_io.elapsed().as_secs_f64().max(0.001);
        let now_io = read_diskstats();
        let drives = self
            .drives
            .iter()
            .map(|d| {
                let (r, w, t) = now_io.get(&d.name).copied().unwrap_or_default();
                let (pr, pw, pt) = self.prev_io.get(&d.name).copied().unwrap_or((r, w, t));
                DriveInfo {
                    name: d.name.clone(),
                    model: d.model.clone(),
                    kind: d.kind.clone(),
                    size: d.size,
                    read_sec: r.saturating_sub(pr) as f64 * 512.0 / dt,
                    write_sec: w.saturating_sub(pw) as f64 * 512.0 / dt,
                    active_pct: ((t.saturating_sub(pt)) as f64 / (dt * 1000.0) * 100.0).clamp(0.0, 100.0) as f32,
                }
            })
            .collect();
        self.prev_io = now_io;
        self.last_io = Instant::now();

        // ---- Network
        let ndt = self.last_net.elapsed().as_secs_f64().max(0.001);
        self.networks.refresh(true);
        self.last_net = Instant::now();
        let mut net: Option<NetStats> = None;
        let mut best_total = 0u64;
        let mut ifaces = Vec::new();
        for (name, data) in self.networks.iter() {
            if name == "lo" {
                continue;
            }
            let total = data.total_received() + data.total_transmitted();
            if net.is_none() || total > best_total {
                best_total = total;
                net = Some(NetStats {
                    iface: name.clone(),
                    rx_bytes: data.total_received(),
                    tx_bytes: data.total_transmitted(),
                    rx_sec: data.received() as f64 / ndt,
                    tx_sec: data.transmitted() as f64 / ndt,
                });
            }
            ifaces.push(IfaceInfo {
                name: name.clone(),
                state: read_trim(&format!("/sys/class/net/{name}/operstate")).unwrap_or_else(|| "unknown".into()),
                speed_mbps: read_trim(&format!("/sys/class/net/{name}/speed")).and_then(|s| s.parse::<i64>().ok()).filter(|s| *s > 0).map(|s| s as u64),
                mac: data.mac_address().to_string(),
                ips: data.ip_networks().iter().map(|ip| ip.addr.to_string()).collect(),
            });
        }
        ifaces.sort_by(|a: &IfaceInfo, b: &IfaceInfo| a.name.cmp(&b.name));

        // ---- Temperature (best effort: CPU package / Tctl, else first sensor)
        let temp = self
            .components
            .list()
            .iter()
            .find(|c| {
                let l = c.label().to_lowercase();
                l.contains("package") || l.contains("tctl") || l.contains("cpu")
            })
            .or_else(|| self.components.list().first())
            .and_then(|c| c.temperature());

        SystemSnapshot {
            hostname: self.hostname.clone(),
            os: self.os.clone(),
            cpu,
            mem,
            filesystems,
            drives,
            net,
            ifaces,
            proc_count: count_processes(),
            uptime: System::uptime(),
            temp,
        }
    }

    pub fn processes(&mut self) -> Vec<ProcInfo> {
        self.psys.refresh_processes(ProcessesToUpdate::All, true);
        let ncpu = self.sys.cpus().len().max(1) as f32;
        let total_mem = self.sys.total_memory().max(1) as f32;
        let mut list: Vec<ProcInfo> = self
            .psys
            .processes()
            .values()
            .map(|p| {
                let cmd = p.cmd().iter().map(|s| s.to_string_lossy().to_string()).collect::<Vec<_>>().join(" ");
                ProcInfo {
                    pid: p.pid().as_u32(),
                    name: p.name().to_string_lossy().to_string(),
                    user: p
                        .user_id()
                        .and_then(|u| self.users.get_user_by_id(u))
                        .map(|u| u.name().to_string())
                        .unwrap_or_default(),
                    cpu: (p.cpu_usage() / ncpu * 10.0).round() / 10.0,
                    mem_pct: (p.memory() as f32 / total_mem * 1000.0).round() / 10.0,
                    mem_bytes: p.memory(),
                    command: if cmd.is_empty() { p.name().to_string_lossy().to_string() } else { cmd },
                }
            })
            .collect();
        list.sort_by(|a, b| b.cpu.partial_cmp(&a.cpu).unwrap_or(std::cmp::Ordering::Equal));
        list
    }

    pub fn kill(&mut self, pid: u32) -> Result<(), String> {
        if pid == 0 {
            return Err("Invalid PID".into());
        }
        match self.psys.process(Pid::from_u32(pid)) {
            Some(p) => {
                if p.kill() {
                    Ok(())
                } else {
                    Err(format!("Could not kill process {pid} (permission denied?)"))
                }
            }
            None => Err(format!("Process {pid} not found")),
        }
    }
}

// ---------------------------------------------------------------- GPU (radeontop)

fn first_f32(s: &str) -> f32 {
    s.split_whitespace()
        .next()
        .map(|w| w.trim_end_matches(|c: char| !c.is_ascii_digit()))
        .and_then(|w| w.parse().ok())
        .unwrap_or(0.0)
}

fn second_f32(s: &str) -> f32 {
    s.split_whitespace()
        .nth(1)
        .map(|w| w.trim_end_matches(|c: char| !c.is_ascii_digit()))
        .and_then(|w| w.parse().ok())
        .unwrap_or(0.0)
}

fn run_radeontop() -> Result<String, String> {
    let args = ["-d", "-", "-l", "1"];
    let direct = Command::new("radeontop").args(args).output();
    if let Ok(o) = &direct {
        let s = String::from_utf8_lossy(&o.stdout).to_string();
        if s.contains("gpu ") {
            return Ok(s);
        }
    }
    match Command::new("sudo").arg("-n").arg("radeontop").args(args).output() {
        Ok(o) => {
            let s = String::from_utf8_lossy(&o.stdout).to_string();
            if s.contains("gpu ") {
                Ok(s)
            } else {
                Err("radeontop returned no data (needs root or passwordless sudo)".into())
            }
        }
        Err(e) => Err(format!("radeontop unavailable: {e}")),
    }
}

fn parse_radeontop(out: &str, g: &mut GpuInfo) {
    let Some(line) = out.lines().find(|l| l.contains("gpu ")) else { return };
    let body = line.split_once(": ").map(|(_, b)| b).unwrap_or(line);
    for tok in body.split(',') {
        let tok = tok.trim();
        let (key, rest) = tok.split_once(' ').unwrap_or((tok, ""));
        let v = first_f32(rest);
        match key {
            "gpu" => g.gfx = v,
            "ee" => g.event = v,
            "vgt" => g.vgt = v,
            "ta" => g.ta = v,
            "sx" => g.sx = v,
            "sh" => g.sci = v,
            "spi" => g.si = v,
            "sc" => g.sc = v,
            "pa" => g.pa = v,
            "db" => g.db = v,
            "cb" => g.cb = v,
            "vram" => g.vram_used_mb = second_f32(rest),
            "mclk" => g.mclk_ghz = second_f32(rest),
            "sclk" => g.sclk_ghz = second_f32(rest),
            _ => {}
        }
    }
}

/// Static GPU identity from sysfs (+ lspci for the marketing name when available).
fn detect_gpu() -> GpuInfo {
    let mut g = GpuInfo::default();
    let mut cards: Vec<String> = fs::read_dir("/sys/class/drm")
        .map(|rd| {
            rd.flatten()
                .map(|e| e.file_name().to_string_lossy().to_string())
                .filter(|n| n.starts_with("card") && n[4..].bytes().all(|b| b.is_ascii_digit()))
                .collect()
        })
        .unwrap_or_default();
    cards.sort();
    let pick = cards
        .iter()
        .find(|c| read_trim(&format!("/sys/class/drm/{c}/device/vendor")).as_deref() == Some("0x1002"))
        .or_else(|| cards.first());
    let Some(card) = pick else { return g };
    let dev = format!("/sys/class/drm/{card}/device");
    let uevent = fs::read_to_string(format!("{dev}/uevent")).unwrap_or_default();
    let field = |k: &str| {
        uevent
            .lines()
            .find_map(|l| l.strip_prefix(&format!("{k}=")))
            .unwrap_or("")
            .to_string()
    };
    g.bus = field("PCI_SLOT_NAME");
    g.driver = field("DRIVER");
    g.vendor = match read_trim(&format!("{dev}/vendor")).as_deref() {
        Some("0x1002") => "AMD".into(),
        Some("0x10de") => "NVIDIA".into(),
        Some("0x8086") => "Intel".into(),
        Some(o) => o.to_string(),
        None => "Unknown".into(),
    };
    g.vram_total_mb = read_trim(&format!("{dev}/mem_info_vram_total"))
        .and_then(|s| s.parse::<f64>().ok())
        .map(|b| (b / 1048576.0) as f32)
        .unwrap_or(0.0);
    g.model = Command::new("lspci")
        .args(["-mm", "-s", &g.bus])
        .output()
        .ok()
        .and_then(|o| {
            let s = String::from_utf8_lossy(&o.stdout).to_string();
            let parts: Vec<&str> = s.split('"').collect();
            parts.get(5).map(|m| m.to_string())
        })
        .unwrap_or_else(|| "Unknown GPU".into());
    g
}

/// Starts a background thread that keeps `store` updated about once a second.
pub fn spawn_gpu_poller(store: Arc<Mutex<GpuInfo>>) {
    std::thread::spawn(move || {
        let base = detect_gpu();
        loop {
            let mut g = base.clone();
            let delay = match run_radeontop() {
                Ok(out) => {
                    g.available = true;
                    parse_radeontop(&out, &mut g);
                    Duration::from_millis(200)
                }
                Err(e) => {
                    g.error = Some(e);
                    Duration::from_secs(5)
                }
            };
            if let Ok(mut s) = store.lock() {
                *s = g;
            }
            std::thread::sleep(delay);
        }
    });
}
