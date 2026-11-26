//! System metrics collection (replaces `systeminformation` + `radeontop` glue from main.js).

use std::collections::HashMap;
use std::fs;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use shared::*;
use sysinfo::{Components, Disks, Networks, Pid, ProcessesToUpdate, System, Users};

/// [reads done, sectors read, ms reading, writes done, sectors written, ms writing, ms doing I/O]
type IoCounters = [u64; 7];

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
            map.insert(f[2].to_string(), [p(3), p(5), p(6), p(7), p(9), p(10), p(12)]);
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

/// Physical drive name (e.g. "nvme0n1") behind a block device path such as
/// /dev/nvme0n1p2, /dev/mapper/root or /dev/md0. Follows device-mapper/RAID slaves.
fn parent_drive(device: &str) -> Option<String> {
    let real = fs::canonicalize(device).ok()?;
    let name = real.file_name()?.to_string_lossy().to_string();
    block_root(&name, 0)
}

fn block_root(name: &str, depth: u8) -> Option<String> {
    if depth > 4 {
        return None;
    }
    if let Ok(mut rd) = fs::read_dir(format!("/sys/class/block/{name}/slaves")) {
        if let Some(Ok(e)) = rd.next() {
            return block_root(&e.file_name().to_string_lossy(), depth + 1);
        }
    }
    // Partition path is .../block/<disk>/<part>; a whole disk is .../block/<disk>.
    let real = fs::canonicalize(format!("/sys/class/block/{name}")).ok()?;
    let parent = real.parent()?.file_name()?.to_string_lossy().to_string();
    if parent == "block" {
        Some(name.to_string())
    } else {
        Some(parent)
    }
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

        // ---- Filesystems (one row per backing device: bind mounts and subvolumes are folded)
        const SKIP_FS: [&str; 6] = ["tmpfs", "devtmpfs", "squashfs", "overlay", "efivarfs", "ramfs"];
        let mut filesystems: Vec<FsInfo> = self
            .disks
            .list()
            .iter()
            .filter(|d| {
                let fs = d.file_system().to_string_lossy();
                d.total_space() > 0 && !SKIP_FS.contains(&fs.as_ref())
            })
            .map(|d| {
                let size = d.total_space();
                let free = d.available_space();
                let used = size.saturating_sub(free);
                let dev = d.name().to_string_lossy().to_string();
                let dev_path = if dev.starts_with('/') { dev.clone() } else { format!("/dev/{dev}") };
                FsInfo {
                    mount: d.mount_point().to_string_lossy().to_string(),
                    fs: d.file_system().to_string_lossy().to_string(),
                    kind: format!("{:?}", d.kind()),
                    device: dev,
                    drive: parent_drive(&dev_path).unwrap_or_default(),
                    size,
                    used,
                    free,
                    use_pct: if size > 0 { used as f32 / size as f32 * 100.0 } else { 0.0 },
                }
            })
            .collect();
        filesystems.sort_by_key(|f| f.mount.len());
        let mut seen = std::collections::HashSet::new();
        filesystems.retain(|f| f.device.is_empty() || seen.insert(f.device.clone()));

        // ---- Physical drives (real I/O from /proc/diskstats)
        let dt = self.last_io.elapsed().as_secs_f64().max(0.001);
        let now_io = read_diskstats();
        let drives = self
            .drives
            .iter()
            .map(|d| {
                let c = now_io.get(&d.name).copied().unwrap_or_default();
                let p = self.prev_io.get(&d.name).copied().unwrap_or(c);
                let dl = |i: usize| c[i].saturating_sub(p[i]);
                let ios = dl(0) + dl(3);
                let (used, free, fs_total) = filesystems
                    .iter()
                    .filter(|f| f.drive == d.name)
                    .fold((0u64, 0u64, 0u64), |a, f| (a.0 + f.used, a.1 + f.free, a.2 + f.size));
                DriveInfo {
                    name: d.name.clone(),
                    model: d.model.clone(),
                    kind: d.kind.clone(),
                    size: d.size,
                    read_sec: dl(1) as f64 * 512.0 / dt,
                    write_sec: dl(4) as f64 * 512.0 / dt,
                    active_pct: (dl(6) as f64 / (dt * 1000.0) * 100.0).clamp(0.0, 100.0) as f32,
                    resp_ms: if ios > 0 { (dl(2) + dl(5)) as f32 / ios as f32 } else { 0.0 },
                    used,
                    free,
                    fs_total,
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
    const BLOCKS: [(&str, &str); 10] = [
        ("ee", "Event engine"), ("vgt", "Vertex grouper"), ("ta", "Texture addr"), ("sx", "Shader export"),
        ("sh", "Seq instr cache"), ("spi", "Shader interp"), ("sc", "Scan converter"),
        ("pa", "Primitive asm"), ("db", "Depth block"), ("cb", "Color block"),
    ];
    g.blocks.clear();
    for tok in body.split(',') {
        let tok = tok.trim();
        let (key, rest) = tok.split_once(' ').unwrap_or((tok, ""));
        let v = first_f32(rest);
        match key {
            "gpu" => g.gfx = v,
            "vram" => g.vram_used_mb = second_f32(rest),
            "mclk" => g.mclk_ghz = second_f32(rest),
            "sclk" => g.sclk_ghz = second_f32(rest),
            k => {
                if let Some((_, name)) = BLOCKS.iter().find(|(key, _)| *key == k) {
                    g.blocks.push((name.to_string(), v));
                }
            }
        }
    }
}

// ---------------------------------------------------------------- GPU (nvidia-smi)

const NVIDIA_QUERY: &str = "--query-gpu=name,driver_version,pci.bus_id,utilization.gpu,utilization.memory,\
memory.used,memory.total,clocks.current.graphics,clocks.current.memory,temperature.gpu,power.draw";

fn run_nvidia_smi() -> Result<String, String> {
    let out = Command::new("nvidia-smi")
        .args([NVIDIA_QUERY, "--format=csv,noheader,nounits"])
        .output()
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                "nvidia-smi not found (install the NVIDIA driver utilities)".to_string()
            } else {
                format!("nvidia-smi failed: {e}")
            }
        })?;
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if out.status.success() && !text.is_empty() {
        Ok(text)
    } else {
        let err = String::from_utf8_lossy(&out.stderr);
        let first = err.lines().next().unwrap_or("no data").trim().to_string();
        Err(format!("nvidia-smi: {first}"))
    }
}

/// Parse the first GPU line of the CSV produced by `NVIDIA_QUERY`.
fn parse_nvidia_smi(out: &str, g: &mut GpuInfo) -> bool {
    let Some(line) = out.lines().next() else { return false };
    let f: Vec<&str> = line.split(',').map(|x| x.trim()).collect();
    if f.len() < 11 {
        return false;
    }
    // "[N/A]" or "[Not Supported]" fail to parse and become None.
    let num = |i: usize| f[i].parse::<f32>().ok();
    g.vendor = "NVIDIA".into();
    g.model = f[0].to_string();
    g.driver = f[1].to_string();
    g.bus = f[2].to_string();
    g.gfx = num(3).unwrap_or(0.0);
    let mem_ctrl = num(4).unwrap_or(0.0);
    g.vram_used_mb = num(5).unwrap_or(0.0);
    g.vram_total_mb = num(6).unwrap_or(0.0);
    g.sclk_ghz = num(7).unwrap_or(0.0) / 1000.0;
    g.mclk_ghz = num(8).unwrap_or(0.0) / 1000.0;
    g.temp = num(9);
    g.power_w = num(10);
    g.blocks = vec![
        ("Memory controller".to_string(), mem_ctrl),
        ("VRAM in use".to_string(), if g.vram_total_mb > 0.0 { g.vram_used_mb / g.vram_total_mb * 100.0 } else { 0.0 }),
    ];
    true
}

/// Static GPU identity from sysfs (+ lspci for the marketing name when available).
/// Prefers a discrete AMD/NVIDIA card over an Intel iGPU (hybrid laptops).
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
    let vendor_of = |c: &String| read_trim(&format!("/sys/class/drm/{c}/device/vendor"));
    let pick = cards
        .iter()
        .find(|c| matches!(vendor_of(c).as_deref(), Some("0x10de") | Some("0x1002")))
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

#[derive(Clone, Copy, PartialEq)]
enum Backend {
    Nvidia,
    Amd,
    Unsupported,
}

/// One sample for the chosen backend. Err(message) when no data.
fn sample(backend: Backend, base: &GpuInfo) -> Result<GpuInfo, String> {
    let mut g = base.clone();
    match backend {
        Backend::Nvidia => {
            let out = run_nvidia_smi()?;
            if !parse_nvidia_smi(&out, &mut g) {
                return Err("nvidia-smi returned unexpected output".into());
            }
        }
        Backend::Amd => {
            let out = run_radeontop()?;
            parse_radeontop(&out, &mut g);
        }
        Backend::Unsupported => {
            return Err(format!("live stats not supported for {} GPUs yet", base.vendor));
        }
    }
    g.available = true;
    g.error = None;
    Ok(g)
}

/// Starts a background thread that keeps `store` updated about once a second.
pub fn spawn_gpu_poller(store: Arc<Mutex<GpuInfo>>) {
    std::thread::spawn(move || {
        let base = detect_gpu();
        // Vendor from sysfs decides. If unknown (no DRM node), try nvidia-smi first, then radeontop.
        let backends: Vec<Backend> = match base.vendor.as_str() {
            "NVIDIA" => vec![Backend::Nvidia],
            "AMD" => vec![Backend::Amd],
            "Intel" => vec![Backend::Unsupported],
            _ => vec![Backend::Nvidia, Backend::Amd],
        };
        loop {
            let mut result = Err("no GPU backend".to_string());
            for b in &backends {
                result = sample(*b, &base);
                if result.is_ok() {
                    break;
                }
            }
            let (g, delay) = match result {
                Ok(g) => {
                    let d = if backends[0] == Backend::Nvidia || g.vendor == "NVIDIA" {
                        Duration::from_millis(900)
                    } else {
                        Duration::from_millis(200)
                    };
                    (g, d)
                }
                Err(e) => {
                    let mut g = base.clone();
                    g.available = false;
                    g.error = Some(e);
                    (g, Duration::from_secs(5))
                }
            };
            if let Ok(mut s) = store.lock() {
                *s = g;
            }
            std::thread::sleep(delay);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nvidia_line() {
        let mut g = GpuInfo::default();
        let line = "NVIDIA GeForce RTX 3060, 550.54.14, 00000000:01:00.0, 12, 5, 812, 12288, 1807, 7500, 41, 14.52\n";
        assert!(parse_nvidia_smi(line, &mut g));
        assert_eq!(g.model, "NVIDIA GeForce RTX 3060");
        assert_eq!(g.driver, "550.54.14");
        assert_eq!(g.gfx, 12.0);
        assert_eq!(g.vram_total_mb, 12288.0);
        assert!((g.sclk_ghz - 1.807).abs() < 1e-4);
        assert_eq!(g.temp, Some(41.0));
        assert_eq!(g.power_w, Some(14.52));
        assert_eq!(g.blocks.len(), 2);
    }

    #[test]
    fn nvidia_not_supported_fields() {
        let mut g = GpuInfo::default();
        let line = "NVIDIA T400, 535.1, 00000000:02:00.0, 3, [N/A], 100, 4096, 300, 5000, [Not Supported], [N/A]";
        assert!(parse_nvidia_smi(line, &mut g));
        assert_eq!(g.temp, None);
        assert_eq!(g.power_w, None);
        assert_eq!(g.blocks[0].1, 0.0);
    }

    #[test]
    fn nvidia_garbage() {
        let mut g = GpuInfo::default();
        assert!(!parse_nvidia_smi("", &mut g));
        assert!(!parse_nvidia_smi("a, b", &mut g));
    }

    #[test]
    fn radeontop_line() {
        let mut g = GpuInfo::default();
        let out = "1700000000.0: bus 03, gpu 21.67%, ee 0.00%, vgt 3.33%, ta 4.17%, sx 5.00%, sh 0.00%, spi 5.83%, sc 5.00%, pa 3.33%, db 5.00%, cb 5.00%, vram 12.69% 520.04mb, gtt 1.00% 80.00mb, mclk 100.00% 1.000ghz, sclk 90.00% 1.800ghz\n";
        parse_radeontop(out, &mut g);
        assert_eq!(g.gfx, 21.67);
        assert_eq!(g.blocks.len(), 10);
        assert!((g.vram_used_mb - 520.04).abs() < 0.01);
        assert!((g.sclk_ghz - 1.8).abs() < 0.001);
    }
}
