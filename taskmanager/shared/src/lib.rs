//! Types shared between the Tauri backend and the Leptos frontend.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct CpuInfo {
    pub brand: String,
    pub vendor: String,
    pub physical_cores: usize,
    pub logical_cores: usize,
    /// Average current frequency in MHz.
    pub speed_mhz: u64,
    /// Total load, 0..100.
    pub load: f32,
    pub per_core: Vec<f32>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct MemInfo {
    pub total: u64,
    pub used: u64,
    pub available: u64,
    pub swap_total: u64,
    pub swap_used: u64,
}

/// A mounted filesystem.
#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct FsInfo {
    pub mount: String,
    pub fs: String,
    pub kind: String,
    pub size: u64,
    pub used: u64,
    pub use_pct: f32,
}

/// A physical block device with live I/O figures.
#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct DriveInfo {
    pub name: String,
    pub model: String,
    pub kind: String,
    pub size: u64,
    pub read_sec: f64,
    pub write_sec: f64,
    /// Percentage of time the device was busy, 0..100.
    pub active_pct: f32,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct NetStats {
    pub iface: String,
    pub rx_bytes: u64,
    pub tx_bytes: u64,
    pub rx_sec: f64,
    pub tx_sec: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct IfaceInfo {
    pub name: String,
    pub state: String,
    pub speed_mbps: Option<u64>,
    pub mac: String,
    pub ips: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct SystemSnapshot {
    pub hostname: String,
    pub os: String,
    pub cpu: CpuInfo,
    pub mem: MemInfo,
    pub filesystems: Vec<FsInfo>,
    pub drives: Vec<DriveInfo>,
    pub net: Option<NetStats>,
    pub ifaces: Vec<IfaceInfo>,
    pub proc_count: usize,
    pub uptime: u64,
    pub temp: Option<f32>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct ProcInfo {
    pub pid: u32,
    pub name: String,
    pub user: String,
    pub cpu: f32,
    pub mem_pct: f32,
    pub mem_bytes: u64,
    pub command: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct GpuInfo {
    pub available: bool,
    pub error: Option<String>,
    pub vendor: String,
    pub model: String,
    pub bus: String,
    pub driver: String,
    pub vram_total_mb: f32,
    pub vram_used_mb: f32,
    pub gfx: f32,
    pub event: f32,
    pub vgt: f32,
    pub ta: f32,
    pub sx: f32,
    pub sci: f32,
    pub si: f32,
    pub sc: f32,
    pub pa: f32,
    pub db: f32,
    pub cb: f32,
    pub mclk_ghz: f32,
    pub sclk_ghz: f32,
}
