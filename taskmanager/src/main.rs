//! Leptos (CSR/WASM) frontend. Talks to the Tauri backend through `invoke`.

use std::collections::HashMap;

use gloo_timers::future::TimeoutFuture;
use leptos::mount::mount_to_body;
use leptos::prelude::*;
use leptos::task::spawn_local;
use serde::{de::DeserializeOwned, Serialize};
use shared::{GpuInfo, ProcInfo, SystemSnapshot};
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = ["window", "__TAURI__", "core"], catch)]
    async fn invoke(cmd: &str, args: JsValue) -> Result<JsValue, JsValue>;
}

#[derive(Serialize)]
struct NoArgs {}

#[derive(Serialize)]
struct KillArgs {
    pid: u32,
}

async fn call<A: Serialize, T: DeserializeOwned>(cmd: &str, args: &A) -> Result<T, String> {
    let args = serde_wasm_bindgen::to_value(args).map_err(|e| e.to_string())?;
    let out = invoke(cmd, args)
        .await
        .map_err(|e| e.as_string().unwrap_or_else(|| "backend error".into()))?;
    serde_wasm_bindgen::from_value(out).map_err(|e| e.to_string())
}

#[derive(Clone, Copy, PartialEq)]
enum Page {
    Cpu,
    Mem,
    Gpu,
    Disk,
    Net,
    Proc,
    About,
}

const HISTORY: usize = 60;

fn push(sig: RwSignal<Vec<f32>>, v: f32) {
    sig.update(|h| {
        h.push(v);
        if h.len() > HISTORY {
            h.remove(0);
        }
    });
}

fn fmt_bytes(b: f64) -> String {
    if !b.is_finite() || b <= 0.0 {
        return "0 B".into();
    }
    if b < 1024.0 {
        format!("{:.0} B", b)
    } else if b < 1_048_576.0 {
        format!("{:.1} KB", b / 1024.0)
    } else if b < 1_073_741_824.0 {
        format!("{:.1} MB", b / 1_048_576.0)
    } else {
        format!("{:.2} GB", b / 1_073_741_824.0)
    }
}

fn fmt_uptime(s: u64) -> String {
    format!("{}:{:02}:{:02}:{:02}", s / 86400, (s % 86400) / 3600, (s % 3600) / 60, s % 60)
}

fn stat(label: &'static str, value: String) -> impl IntoView {
    view! { <div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value}</div></div> }
}

fn stat_sm(label: &'static str, value: String) -> impl IntoView {
    view! { <div class="stat"><div class="stat-label">{label}</div><div class="stat-value sm">{value}</div></div> }
}

/// SVG line chart; `max` is the value that maps to the top edge.
fn chart(data: Vec<f32>, color: &'static str, max: f32) -> impl IntoView {
    const W: f32 = 600.0;
    const H: f32 = 140.0;
    let step = W / (HISTORY as f32 - 1.0);
    let n = data.len();
    let pts: Vec<String> = data
        .iter()
        .enumerate()
        .map(|(i, v)| {
            let x = W - (n - 1 - i) as f32 * step;
            let y = H - (v / max).clamp(0.0, 1.0) * H;
            format!("{x:.1},{y:.1}")
        })
        .collect();
    let line = pts.join(" ");
    let area = if n > 0 {
        let first_x = W - (n - 1) as f32 * step;
        format!("{first_x:.1},{H} {line} {W},{H}")
    } else {
        String::new()
    };
    view! {
        <svg class="chart" viewBox="0 0 600 140" preserveAspectRatio="none">
            <line x1="0" y1="0" x2="600" y2="0" />
            <line x1="0" y1="35" x2="600" y2="35" />
            <line x1="0" y1="70" x2="600" y2="70" />
            <line x1="0" y1="105" x2="600" y2="105" />
            <line x1="0" y1="140" x2="600" y2="140" />
            <polygon points=area fill=color fill-opacity="0.13" />
            <polyline points=line stroke=color />
        </svg>
    }
}

fn nav(page: RwSignal<Page>, target: Page, icon: &'static str, label: &'static str) -> impl IntoView {
    view! {
        <div class="nav-item" class:active=move || page.get() == target on:click=move |_| page.set(target)>
            <span class="ico">{icon}</span>
            <span>{label}</span>
        </div>
    }
}

fn bar(pct: f32) -> impl IntoView {
    view! { <div class="bar"><div class="bar-fill" style=format!("width:{:.1}%", pct.clamp(0.0, 100.0))></div></div> }
}

#[component]
fn App() -> impl IntoView {
    let page = RwSignal::new(Page::Cpu);
    let snap = RwSignal::new(None::<SystemSnapshot>);
    let procs = RwSignal::new(Vec::<ProcInfo>::new());
    let gpu = RwSignal::new(None::<GpuInfo>);
    let hist_cpu = RwSignal::new(Vec::<f32>::new());
    let hist_mem = RwSignal::new(Vec::<f32>::new());
    let hist_gpu = RwSignal::new(Vec::<f32>::new());
    let hist_net = RwSignal::new(Vec::<f32>::new());
    let hist_disk = RwSignal::new(HashMap::<String, Vec<f32>>::new());
    let selected_drive = RwSignal::new(0usize);
    let search = RwSignal::new(String::new());
    let kill_target = RwSignal::new(None::<(u32, String)>);
    let kill_error = RwSignal::new(None::<String>);

    // Polling loop: system every second; processes/GPU only while their page is open.
    spawn_local(async move {
        loop {
            if let Ok(s) = call::<_, SystemSnapshot>("get_system", &NoArgs {}).await {
                push(hist_cpu, s.cpu.load);
                if s.mem.total > 0 {
                    push(hist_mem, s.mem.used as f32 / s.mem.total as f32 * 100.0);
                }
                if let Some(n) = &s.net {
                    push(hist_net, n.rx_sec as f32);
                }
                hist_disk.update(|m| {
                    for d in &s.drives {
                        let h = m.entry(d.name.clone()).or_default();
                        h.push(d.active_pct);
                        if h.len() > HISTORY {
                            h.remove(0);
                        }
                    }
                });
                snap.set(Some(s));
            }
            match page.get_untracked() {
                Page::Proc => {
                    if let Ok(p) = call::<_, Vec<ProcInfo>>("get_processes", &NoArgs {}).await {
                        procs.set(p);
                    }
                }
                Page::Gpu => {
                    if let Ok(g) = call::<_, GpuInfo>("get_gpu", &NoArgs {}).await {
                        push(hist_gpu, g.gfx);
                        gpu.set(Some(g));
                    }
                }
                _ => {}
            }
            TimeoutFuture::new(1000).await;
        }
    });

    let confirm_kill = move |_| {
        if let Some((pid, _)) = kill_target.get_untracked() {
            spawn_local(async move {
                match call::<_, ()>("kill_process", &KillArgs { pid }).await {
                    Ok(()) => kill_error.set(None),
                    Err(e) => kill_error.set(Some(e)),
                }
                if let Ok(p) = call::<_, Vec<ProcInfo>>("get_processes", &NoArgs {}).await {
                    procs.set(p);
                }
            });
            kill_target.set(None);
        }
    };

    view! {
        <div class="sidebar">
            <div class="brand"><div class="brand-logo">"T"</div>"Task Manager"</div>
            {nav(page, Page::Cpu, "▦", "CPU")}
            {nav(page, Page::Mem, "▤", "Memory")}
            {nav(page, Page::Gpu, "◈", "GPU")}
            {nav(page, Page::Disk, "◉", "Disk")}
            {nav(page, Page::Net, "⇅", "Network")}
            {nav(page, Page::Proc, "☰", "Processes")}
            <div class="nav-spacer"></div>
            {nav(page, Page::About, "ⓘ", "About")}
        </div>

        <div class="main">
            // ---------------------------------------------------------------- CPU
            <div class="page" class:active=move || page.get() == Page::Cpu>
                <h1>"CPU"</h1>
                <p class="para">
                    {move || snap.get().map(|s| format!("{} logical threads available, running at {:.1}% total usage.", s.cpu.logical_cores, s.cpu.load))
                        .unwrap_or_else(|| "Loading CPU information...".into())}
                </p>
                <div class="card">
                    {move || snap.get().map(|s| view! {
                        <div class="row">
                            <div>
                                <div class="title">{s.cpu.brand.clone()}</div>
                                <div class="sub">{format!("Vendor: {} · Host: {} · {}", s.cpu.vendor, s.hostname, s.os)}</div>
                            </div>
                            <div class="mono">{s.temp.map(|t| format!("{t:.0} °C"))}</div>
                        </div>
                    })}
                </div>
                <div class="grid-4 mb">
                    {move || snap.get().map(|s| view! {
                        {stat("Utilization", format!("{:.1}%", s.cpu.load))}
                        {stat("Speed", format!("{:.2} GHz", s.cpu.speed_mhz as f64 / 1000.0))}
                        {stat("Processes", s.proc_count.to_string())}
                        {stat_sm("Uptime", fmt_uptime(s.uptime))}
                    })}
                </div>
                <div class="grid-4 mb">
                    {move || snap.get().map(|s| view! {
                        {stat("Cores", s.cpu.physical_cores.to_string())}
                        {stat("Threads", s.cpu.logical_cores.to_string())}
                        {stat("Memory in use", format!("{:.1}%", s.mem.used as f64 / s.mem.total.max(1) as f64 * 100.0))}
                        {stat("Temperature", s.temp.map(|t| format!("{t:.0} °C")).unwrap_or_else(|| "—".into()))}
                    })}
                </div>
                <h2>"Usage History"</h2>
                {move || chart(hist_cpu.get(), "#58a6ff", 100.0)}
                <h2>"Per-core Load"</h2>
                <div class="grid-4">
                    {move || snap.get().map(|s| s.cpu.per_core.iter().enumerate().map(|(i, l)| view! {
                        <div class="stat">
                            <div class="stat-label">{format!("Core {i}")}</div>
                            <div class="stat-value sm">{format!("{l:.1}%")}</div>
                            {bar(*l)}
                        </div>
                    }).collect_view())}
                </div>
            </div>

            // ------------------------------------------------------------- Memory
            <div class="page" class:active=move || page.get() == Page::Mem>
                <h1>"Memory"</h1>
                <p class="para">
                    {move || snap.get().map(|s| {
                        let m = s.mem;
                        format!("{} of {} in use ({:.1}%). Available: {}. Swap: {} of {}.",
                            fmt_bytes(m.used as f64), fmt_bytes(m.total as f64),
                            m.used as f64 / m.total.max(1) as f64 * 100.0,
                            fmt_bytes(m.available as f64), fmt_bytes(m.swap_used as f64), fmt_bytes(m.swap_total as f64))
                    }).unwrap_or_else(|| "Loading memory information...".into())}
                </p>
                <div class="grid-4">
                    {move || snap.get().map(|s| view! {
                        {stat("Total", fmt_bytes(s.mem.total as f64))}
                        {stat("Used", fmt_bytes(s.mem.used as f64))}
                        {stat("Available", fmt_bytes(s.mem.available as f64))}
                        {stat("Usage", format!("{:.1}%", s.mem.used as f64 / s.mem.total.max(1) as f64 * 100.0))}
                    })}
                </div>
                <h2>"Usage History"</h2>
                {move || chart(hist_mem.get(), "#a371f7", 100.0)}
                <h2>"Swap"</h2>
                <div class="card">
                    {move || snap.get().map(|s| {
                        let pct = if s.mem.swap_total > 0 { s.mem.swap_used as f32 / s.mem.swap_total as f32 * 100.0 } else { 0.0 };
                        view! {
                            <div class="row">
                                <div class="title">"Swap space"</div>
                                <div class="mono">{format!("{} / {}", fmt_bytes(s.mem.swap_used as f64), fmt_bytes(s.mem.swap_total as f64))}</div>
                            </div>
                            {bar(pct)}
                        }
                    })}
                </div>
            </div>

            // ---------------------------------------------------------------- GPU
            <div class="page" class:active=move || page.get() == Page::Gpu>
                <h1>"GPU"</h1>
                <p class="para">
                    {move || match gpu.get() {
                        None => "Loading GPU information...".to_string(),
                        Some(g) if !g.available => format!("GPU stats unavailable: {}", g.error.unwrap_or_else(|| "offline".into())),
                        Some(g) => format!("Graphics pipe at {:.1}%, VRAM {:.0}M / {:.0}M. Memory clock {:.2} GHz, shader clock {:.2} GHz.",
                            g.gfx, g.vram_used_mb, g.vram_total_mb, g.mclk_ghz, g.sclk_ghz),
                    }}
                </p>
                <div class="card">
                    {move || gpu.get().map(|g| view! {
                        <div class="row">
                            <div>
                                <div class="title">{g.model.clone()}</div>
                                <div class="sub">{format!("{} · {}", g.vendor, g.bus)}</div>
                            </div>
                            <div class="mono">
                                <div>{if g.vram_total_mb > 0.0 { format!("{:.0} MB detected", g.vram_total_mb) } else { "VRAM unknown".into() }}</div>
                                <div class="sub">{if g.driver.is_empty() { String::new() } else { format!("Driver {}", g.driver) }}</div>
                            </div>
                        </div>
                    })}
                </div>
                <div class="grid-4">
                    {move || gpu.get().filter(|g| g.available).map(|g| view! {
                        {stat("GPU Load", format!("{:.1}%", g.gfx))}
                        {stat("VRAM", format!("{:.0}/{:.0}M", g.vram_used_mb, g.vram_total_mb))}
                        {stat("Mem Clock", format!("{:.2} GHz", g.mclk_ghz))}
                        {stat("Shader Clock", format!("{:.2} GHz", g.sclk_ghz))}
                    })}
                </div>
                <h2>"GPU Load History"</h2>
                {move || chart(hist_gpu.get(), "#f85149", 100.0)}
                <h2>"Pipeline Blocks"</h2>
                <div class="grid-4">
                    {move || gpu.get().filter(|g| g.available).map(|g| {
                        [("Event Engine", g.event), ("Vertex Grouper", g.vgt), ("Texture Addr", g.ta),
                         ("Shader Export", g.sx), ("Seq Instr Cache", g.sci), ("Shader Interp", g.si),
                         ("Scan Converter", g.sc), ("Primitive Asm", g.pa), ("Depth Block", g.db), ("Color Block", g.cb)]
                            .into_iter()
                            .map(|(name, v)| view! {
                                <div class="stat">
                                    <div class="stat-label">{name}</div>
                                    <div class="stat-value">{format!("{v:.1}%")}</div>
                                    {bar(v)}
                                </div>
                            })
                            .collect_view()
                    })}
                </div>
            </div>

            // --------------------------------------------------------------- Disk
            <div class="page" class:active=move || page.get() == Page::Disk>
                <h1>"Disk"</h1>
                <p class="para">
                    {move || snap.get().and_then(|s| s.drives.get(selected_drive.get()).cloned()).map(|d|
                        format!("Active Time: {:.1}% · Read Rate: {}/s · Write Rate: {}/s", d.active_pct, fmt_bytes(d.read_sec), fmt_bytes(d.write_sec)))
                        .unwrap_or_else(|| "Loading disk information...".into())}
                </p>
                <div class="section-header-flex">
                    <h2>
                        "Disk Activity "
                        <span style="color:var(--accent);font-size:0.8rem;text-transform:none">
                            {move || snap.get().and_then(|s| s.drives.get(selected_drive.get()).map(|d| format!("— {}", d.name)))}
                        </span>
                    </h2>
                    <div class="outside-badge">
                        {move || snap.get().and_then(|s| s.drives.get(selected_drive.get()).map(|d| format!("{:.1}%", d.active_pct))).unwrap_or_else(|| "0.0%".into())}
                    </div>
                </div>
                {move || {
                    let name = snap.get().and_then(|s| s.drives.get(selected_drive.get()).map(|d| d.name.clone())).unwrap_or_default();
                    chart(hist_disk.get().get(&name).cloned().unwrap_or_default(), "#d29922", 100.0)
                }}
                <h2>"Physical Drives"</h2>
                <div class="grid-2">
                    {move || snap.get().map(|s| s.drives.iter().enumerate().map(|(i, d)| {
                        let label = if d.model.is_empty() { d.name.clone() } else { format!("{} ({})", d.model, d.name) };
                        view! {
                            <div class="card drive-card" class:active=move || selected_drive.get() == i on:click=move |_| selected_drive.set(i)>
                                <div class="row">
                                    <div class="title">{label}</div>
                                    <span class="badge badge-low">{d.kind.clone()}</span>
                                </div>
                                <div class="sub">{format!("Read {}/s · Write {}/s", fmt_bytes(d.read_sec), fmt_bytes(d.write_sec))}</div>
                                <div class="mono left">{fmt_bytes(d.size as f64)}</div>
                            </div>
                        }
                    }).collect_view())}
                </div>
                <h2>"Filesystems Capacity"</h2>
                <div>
                    {move || snap.get().map(|s| s.filesystems.iter().map(|d| view! {
                        <div class="card">
                            <div class="row">
                                <div>
                                    <div class="title">{d.mount.clone()}</div>
                                    <div class="sub">{format!("{} · {}", d.fs, d.kind)}</div>
                                </div>
                                <div class="mono">
                                    <div>{format!("{} / {}", fmt_bytes(d.used as f64), fmt_bytes(d.size as f64))}</div>
                                    <div class="sub">{format!("{:.1}% used", d.use_pct)}</div>
                                </div>
                            </div>
                            {bar(d.use_pct)}
                        </div>
                    }).collect_view())}
                </div>
            </div>

            // ------------------------------------------------------------ Network
            <div class="page" class:active=move || page.get() == Page::Net>
                <h1>"Network"</h1>
                <p class="para">
                    {move || snap.get().and_then(|s| s.net).map(|n| format!(
                        "Interface {}. Received {} total, sent {} total. Current rate: {}/s down, {}/s up.",
                        n.iface, fmt_bytes(n.rx_bytes as f64), fmt_bytes(n.tx_bytes as f64), fmt_bytes(n.rx_sec), fmt_bytes(n.tx_sec)))
                        .unwrap_or_else(|| "Loading network information...".into())}
                </p>
                <h2>"Network Traffic (download)"</h2>
                {move || {
                    let h = hist_net.get();
                    let max = h.iter().cloned().fold(1_048_576.0_f32, f32::max);
                    chart(h, "#3fb950", max)
                }}
                <div class="grid-4" style="margin-top:12px">
                    {move || snap.get().and_then(|s| s.net).map(|n| view! {
                        {stat("Interface", n.iface.clone())}
                        {stat("RX Total", fmt_bytes(n.rx_bytes as f64))}
                        {stat("TX Total", fmt_bytes(n.tx_bytes as f64))}
                        {stat("RX Rate", format!("{}/s", fmt_bytes(n.rx_sec)))}
                        {stat("TX Rate", format!("{}/s", fmt_bytes(n.tx_sec)))}
                    })}
                </div>
                <h2>"Interfaces"</h2>
                <div class="grid-2">
                    {move || snap.get().map(|s| s.ifaces.iter().map(|i| {
                        let up = i.state == "up";
                        view! {
                            <div class="card">
                                <div class="row">
                                    <div class="title">{i.name.clone()}</div>
                                    <span class="badge" class:badge-low=up class:badge-med=!up>{i.state.clone()}</span>
                                </div>
                                <div class="sub">{format!("{} · MAC {}", i.speed_mbps.map(|s| format!("{s} Mbps")).unwrap_or_else(|| "speed unknown".into()), i.mac)}</div>
                                <div class="mono left">
                                    {if i.ips.is_empty() { "no address".to_string() } else { i.ips.join(" · ") }}
                                </div>
                            </div>
                        }
                    }).collect_view())}
                </div>
            </div>

            // ---------------------------------------------------------- Processes
            <div class="page" class:active=move || page.get() == Page::Proc>
                <h1>"Processes"</h1>
                <div class="proc-header">
                    <p class="para" style="margin-bottom:0">
                        {move || {
                            let q = search.get().to_lowercase();
                            let total = procs.get().len();
                            if q.trim().is_empty() {
                                format!("{total} processes running. Sorted by CPU usage.")
                            } else {
                                let n = procs.get().iter().filter(|p| matches_query(p, q.trim())).count();
                                format!("{n} processes matching \"{}\" ({total} total).", q.trim())
                            }
                        }}
                    </p>
                    <div class="search-container">
                        <input type="text" class="search-input" placeholder="Search processes..."
                            prop:value=move || search.get()
                            on:input:target=move |ev| search.set(ev.target().value()) />
                        <span class="search-clear" style:display=move || if search.get().is_empty() { "none" } else { "block" }
                            on:click=move |_| search.set(String::new())>"✕"</span>
                    </div>
                </div>
                {move || kill_error.get().map(|e| view! { <div class="error">{e}</div> })}
                <div class="proc-table">
                    <table>
                        <thead><tr>
                            <th>"PID"</th><th>"Name"</th><th>"User"</th><th>"CPU %"</th><th>"Mem %"</th><th>"Memory"</th><th>"Actions"</th>
                        </tr></thead>
                        <tbody>
                            {move || {
                                let q = search.get().to_lowercase();
                                let q = q.trim().to_string();
                                procs.get().into_iter().filter(|p| matches_query(p, &q)).take(80).map(|p| {
                                    let badge = if p.cpu > 20.0 { "badge badge-high" } else if p.cpu > 5.0 { "badge badge-med" } else { "badge badge-low" };
                                    let (pid, name) = (p.pid, p.name.clone());
                                    view! {
                                        <tr>
                                            <td>{p.pid}</td>
                                            <td title=p.command.clone()>{p.name.clone()}</td>
                                            <td>{if p.user.is_empty() { "—".to_string() } else { p.user.clone() }}</td>
                                            <td><span class=badge>{format!("{:.1}%", p.cpu)}</span></td>
                                            <td>{format!("{:.1}%", p.mem_pct)}</td>
                                            <td>{fmt_bytes(p.mem_bytes as f64)}</td>
                                            <td><button on:click=move |_| kill_target.set(Some((pid, name.clone())))>"Kill"</button></td>
                                        </tr>
                                    }
                                }).collect_view()
                            }}
                        </tbody>
                    </table>
                </div>
            </div>

            // -------------------------------------------------------------- About
            <div class="page" class:active=move || page.get() == Page::About>
                <h1>"About"</h1>
                <p class="para">"Version: 1.0.3: Task Manager for Desktop Systems."</p>
                <div class="card">
                    <p style="line-height:1.8">
                        "System Monitor Application Panel." <br />
                        "For bug reports, please check the local development repository." <br /><br />
                        "This task manager monitors system performance metrics dynamically. Built with Rust, Tauri and Leptos."
                    </p>
                </div>
            </div>
        </div>

        {move || kill_target.get().map(|(pid, name)| view! {
            <div class="modal-backdrop">
                <div class="modal">
                    <p>{format!("Kill process {pid} ({name})?")}</p>
                    <div class="actions">
                        <button on:click=move |_| kill_target.set(None)>"Cancel"</button>
                        <button on:click=confirm_kill>"Kill"</button>
                    </div>
                </div>
            </div>
        })}
    }
}

fn matches_query(p: &ProcInfo, q: &str) -> bool {
    q.is_empty()
        || p.name.to_lowercase().contains(q)
        || p.pid.to_string().contains(q)
        || p.user.to_lowercase().contains(q)
}

fn main() {
    mount_to_body(App);
}
