//! Leptos (CSR/WASM) frontend. Talks to the Tauri backend through `invoke`.

use std::cmp::Ordering;
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
    Proc,
    Cpu,
    Mem,
    Disk,
    Gpu,
    Net,
    About,
}

#[derive(Clone, Copy, PartialEq)]
enum SortKey {
    Pid,
    Name,
    User,
    Cpu,
    Mem,
}

const HISTORY: usize = 60;

// ------------------------------------------------------------------ helpers

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
        format!("{:.1} GB", b / 1_073_741_824.0)
    }
}

/// Largest value in both series, never below 1 MB/s so an idle graph stays flat.
fn peak(a: &[f32], b: &[f32]) -> f32 {
    a.iter().chain(b.iter()).cloned().fold(1_048_576.0_f32, f32::max)
}

fn fmt_rate(b: f64) -> String {
    format!("{}/s", fmt_bytes(b))
}

fn fmt_uptime(s: u64) -> String {
    format!("{}:{:02}:{:02}:{:02}", s / 86400, (s % 86400) / 3600, (s % 3600) / 60, s % 60)
}

fn pct_of(a: u64, b: u64) -> f32 {
    if b == 0 {
        0.0
    } else {
        a as f32 / b as f32 * 100.0
    }
}

/// Turn a history into SVG polyline + filled-area points for a w x h box.
fn series(data: &[f32], max: f32, w: f32, h: f32) -> (String, String) {
    let n = data.len();
    if n < 2 {
        return (String::new(), String::new());
    }
    let step = w / (HISTORY as f32 - 1.0);
    let pts: Vec<String> = data
        .iter()
        .enumerate()
        .map(|(i, v)| {
            let x = w - (n - 1 - i) as f32 * step;
            let y = h - (v / max.max(0.0001)).clamp(0.0, 1.0) * h;
            format!("{x:.1},{y:.1}")
        })
        .collect();
    let first_x = w - (n - 1) as f32 * step;
    let line = pts.join(" ");
    let area = format!("{first_x:.1},{h} {line} {w},{h}");
    (line, area)
}

/// Big graph. `extra` is an optional second line (e.g. upload).
fn plot(data: Vec<f32>, extra: Vec<f32>, max: f32) -> impl IntoView {
    let (line, area) = series(&data, max, 600.0, 200.0);
    let (line2, _) = series(&extra, max, 600.0, 200.0);
    view! {
        <svg class="plot" viewBox="0 0 600 200" preserveAspectRatio="none">
            {(1..10).map(|i| {
                let x = (i as f32 * 60.0).to_string();
                view! { <line x1=x.clone() y1="0" x2=x y2="200" /> }
            }).collect_view()}
            {(1..4).map(|i| {
                let y = (i as f32 * 50.0).to_string();
                view! { <line x1="0" y1=y.clone() x2="600" y2=y /> }
            }).collect_view()}
            <polygon points=area />
            <polyline points=line />
            <polyline class="b" points=line2 />
        </svg>
    }
}

/// Tiny graph for the resource list.
fn spark(data: Vec<f32>, max: f32) -> impl IntoView {
    let (line, area) = series(&data, max, 60.0, 36.0);
    view! {
        <svg viewBox="0 0 60 36" preserveAspectRatio="none">
            <polygon points=area />
            <polyline points=line />
        </svg>
    }
}

fn head(title: &'static str, right: impl Fn() -> String + Send + Sync + 'static) -> impl IntoView {
    view! {
        <div class="dhead">
            <h1>{title}</h1>
            <div class="dmodel">{right}</div>
        </div>
    }
}

fn axis(left: &'static str, right: impl Fn() -> String + Send + Sync + 'static) -> impl IntoView {
    view! { <div class="axis"><span>{left}</span><span>{right}</span></div> }
}

fn fact(label: &'static str, value: String) -> impl IntoView {
    view! { <div class="fact"><div class="fl">{label}</div><div class="fv">{value}</div></div> }
}

fn kv(k: &'static str, v: String) -> impl IntoView {
    view! { <div class="kv"><span>{k}</span><span>{v}</span></div> }
}

fn bar(pct: f32) -> impl IntoView {
    view! { <div class="bar"><i style=format!("width:{:.1}%", pct.clamp(0.0, 100.0))></i></div> }
}

fn res_item<S, D>(page: RwSignal<Page>, target: Page, name: &'static str, cls: &'static str, data: S, detail: D) -> impl IntoView
where
    S: Fn() -> (Vec<f32>, f32) + Send + Sync + 'static,
    D: Fn() -> String + Send + Sync + 'static,
{
    view! {
        <div class=format!("res {cls}") class:sel=move || page.get() == target on:click=move |_| page.set(target)>
            <div class="spark">{move || { let (d, m) = data(); spark(d, m) }}</div>
            <div class="rtxt">
                <div class="rname">{name}</div>
                <div class="rdet">{detail}</div>
            </div>
        </div>
    }
}

fn plain_item(page: RwSignal<Page>, target: Page, name: &'static str) -> impl IntoView {
    view! {
        <div class="plain" class:sel=move || page.get() == target on:click=move |_| page.set(target)>{name}</div>
    }
}

fn th(label: &'static str, key: SortKey, num: bool, sort_key: RwSignal<SortKey>, sort_desc: RwSignal<bool>) -> impl IntoView {
    view! {
        <th class:num=move || num on:click=move |_| {
            if sort_key.get_untracked() == key {
                sort_desc.update(|d| *d = !*d);
            } else {
                sort_key.set(key);
                sort_desc.set(key != SortKey::Name && key != SortKey::User);
            }
        }>
            {label}
            {move || if sort_key.get() == key { if sort_desc.get() { " ▼" } else { " ▲" } } else { "" }}
        </th>
    }
}

fn matches_query(p: &ProcInfo, q: &str) -> bool {
    q.is_empty() || p.name.to_lowercase().contains(q) || p.pid.to_string().contains(q) || p.user.to_lowercase().contains(q)
}

// ---------------------------------------------------------------------- app

#[component]
fn App() -> impl IntoView {
    let page = RwSignal::new(Page::Proc);
    let snap = RwSignal::new(None::<SystemSnapshot>);
    let procs = RwSignal::new(Vec::<ProcInfo>::new());
    let gpu = RwSignal::new(None::<GpuInfo>);
    let hist_cpu = RwSignal::new(Vec::<f32>::new());
    let hist_mem = RwSignal::new(Vec::<f32>::new());
    let hist_gpu = RwSignal::new(Vec::<f32>::new());
    let hist_rx = RwSignal::new(Vec::<f32>::new());
    let hist_tx = RwSignal::new(Vec::<f32>::new());
    let hist_disk = RwSignal::new(HashMap::<String, Vec<f32>>::new());
    let hist_dr = RwSignal::new(HashMap::<String, Vec<f32>>::new());
    let hist_dw = RwSignal::new(HashMap::<String, Vec<f32>>::new());
    let drive = RwSignal::new(0usize);
    let search = RwSignal::new(String::new());
    let sort_key = RwSignal::new(SortKey::Cpu);
    let sort_desc = RwSignal::new(true);
    let selected = RwSignal::new(None::<u32>);
    let kill_target = RwSignal::new(None::<(u32, String)>);
    let kill_error = RwSignal::new(None::<String>);

    // One loop: system + GPU every second, process list only while that page is open.
    spawn_local(async move {
        loop {
            if let Ok(s) = call::<_, SystemSnapshot>("get_system", &NoArgs {}).await {
                push(hist_cpu, s.cpu.load);
                push(hist_mem, pct_of(s.mem.used, s.mem.total));
                if let Some(n) = &s.net {
                    push(hist_rx, n.rx_sec as f32);
                    push(hist_tx, n.tx_sec as f32);
                }
                for (sig, f) in [
                    (hist_disk, (|d: &shared::DriveInfo| d.active_pct) as fn(&shared::DriveInfo) -> f32),
                    (hist_dr, |d: &shared::DriveInfo| d.read_sec as f32),
                    (hist_dw, |d: &shared::DriveInfo| d.write_sec as f32),
                ] {
                    sig.update(|m| {
                        for d in &s.drives {
                            let h = m.entry(d.name.clone()).or_default();
                            h.push(f(d));
                            if h.len() > HISTORY {
                                h.remove(0);
                            }
                        }
                    });
                }
                snap.set(Some(s));
            }
            if let Ok(g) = call::<_, GpuInfo>("get_gpu", &NoArgs {}).await {
                if g.available {
                    push(hist_gpu, g.gfx);
                }
                gpu.set(Some(g));
            }
            if page.get_untracked() == Page::Proc {
                if let Ok(p) = call::<_, Vec<ProcInfo>>("get_processes", &NoArgs {}).await {
                    procs.set(p);
                }
            }
            TimeoutFuture::new(1000).await;
        }
    });

    // Switching to the process page should not wait for the next tick.
    Effect::new(move |_| {
        if page.get() == Page::Proc {
            spawn_local(async move {
                if let Ok(p) = call::<_, Vec<ProcInfo>>("get_processes", &NoArgs {}).await {
                    procs.set(p);
                }
            });
        }
    });

    let ask_kill = move |_| {
        if let Some(pid) = selected.get_untracked() {
            let name = procs.get_untracked().iter().find(|p| p.pid == pid).map(|p| p.name.clone()).unwrap_or_default();
            kill_target.set(Some((pid, name)));
        }
    };
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

    let cur_drive = move || snap.get().and_then(|s| s.drives.get(drive.get()).cloned());

    view! {
        <div class="side">
            <div class="side-title">"Task Manager"</div>
            {plain_item(page, Page::Proc, "Processes")}
            <div class="side-sep">"Performance"</div>
            {res_item(page, Page::Cpu, "CPU", "c-cpu",
                move || (hist_cpu.get(), 100.0),
                move || snap.get().map(|s| format!("{:.0}%  {:.2} GHz", s.cpu.load, s.cpu.speed_mhz as f64 / 1000.0)).unwrap_or_default())}
            {res_item(page, Page::Mem, "Memory", "c-mem",
                move || (hist_mem.get(), 100.0),
                move || snap.get().map(|s| format!("{} / {} ({:.0}%)", fmt_bytes(s.mem.used as f64), fmt_bytes(s.mem.total as f64), pct_of(s.mem.used, s.mem.total))).unwrap_or_default())}
            {res_item(page, Page::Disk, "Disk", "c-disk",
                move || {
                    let name = cur_drive().map(|d| d.name).unwrap_or_default();
                    (hist_disk.get().get(&name).cloned().unwrap_or_default(), 100.0)
                },
                move || cur_drive().map(|d| format!("{} ({})  {:.0}%", d.name, d.kind, d.active_pct)).unwrap_or_default())}
            {res_item(page, Page::Gpu, "GPU", "c-gpu",
                move || (hist_gpu.get(), 100.0),
                move || match gpu.get() {
                    Some(g) if g.available => format!("{:.0}%", g.gfx),
                    _ => "unavailable".to_string(),
                })}
            {res_item(page, Page::Net, "Network", "c-net",
                move || {
                    let rx = hist_rx.get();
                    let max = rx.iter().cloned().fold(65_536.0_f32, f32::max);
                    (rx, max)
                },
                move || snap.get().and_then(|s| s.net).map(|n| format!("R {}  S {}", fmt_rate(n.rx_sec), fmt_rate(n.tx_sec))).unwrap_or_default())}
            <div class="grow"></div>
            {plain_item(page, Page::About, "About")}
        </div>

        <div class="main">
            // ---------------------------------------------------------- Processes
            <div class="page procs" class:active=move || page.get() == Page::Proc>
                <div class="toolbar">
                    <input type="text" placeholder="Search by name, PID or user"
                        prop:value=move || search.get()
                        on:input:target=move |ev| search.set(ev.target().value()) />
                    <span class="count">
                        {move || {
                            let q = search.get().to_lowercase();
                            let q = q.trim().to_string();
                            let n = procs.get().iter().filter(|p| matches_query(p, &q)).count();
                            format!("{n} processes")
                        }}
                    </span>
                    <span class="grow"></span>
                    <button class="danger" prop:disabled=move || selected.get().is_none() on:click=ask_kill>"End task"</button>
                </div>
                {move || kill_error.get().map(|e| view! { <div class="error">{e}</div> })}
                <div class="tablewrap">
                    <table>
                        <thead><tr>
                            {th("PID", SortKey::Pid, true, sort_key, sort_desc)}
                            {th("Name", SortKey::Name, false, sort_key, sort_desc)}
                            {th("User", SortKey::User, false, sort_key, sort_desc)}
                            {th("CPU", SortKey::Cpu, true, sort_key, sort_desc)}
                            {th("Memory", SortKey::Mem, true, sort_key, sort_desc)}
                            <th class="num">"Mem %"</th>
                        </tr></thead>
                        <tbody>
                            {move || {
                                let q = search.get().to_lowercase();
                                let q = q.trim().to_string();
                                let key = sort_key.get();
                                let desc = sort_desc.get();
                                let mut rows: Vec<ProcInfo> = procs.get().into_iter().filter(|p| matches_query(p, &q)).collect();
                                rows.sort_by(|a, b| {
                                    let o = match key {
                                        SortKey::Pid => a.pid.cmp(&b.pid),
                                        SortKey::Name => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
                                        SortKey::User => a.user.cmp(&b.user),
                                        SortKey::Cpu => a.cpu.partial_cmp(&b.cpu).unwrap_or(Ordering::Equal),
                                        SortKey::Mem => a.mem_bytes.cmp(&b.mem_bytes),
                                    };
                                    if desc { o.reverse() } else { o }
                                });
                                rows.into_iter().take(200).map(|p| {
                                    let pid = p.pid;
                                    let cpu_bg = format!("background:rgba(91,155,213,{:.2})", (p.cpu / 100.0 * 3.0).min(1.0) * 0.5);
                                    let mem_bg = format!("background:rgba(155,114,184,{:.2})", (p.mem_pct / 20.0).min(1.0) * 0.45);
                                    view! {
                                        <tr class:sel=move || selected.get() == Some(pid) on:click=move |_| selected.set(Some(pid))>
                                            <td class="num">{p.pid}</td>
                                            <td title=p.command.clone()>{p.name.clone()}</td>
                                            <td class="dim">{if p.user.is_empty() { "-".to_string() } else { p.user.clone() }}</td>
                                            <td class="num" style=cpu_bg>{format!("{:.1}%", p.cpu)}</td>
                                            <td class="num" style=mem_bg>{fmt_bytes(p.mem_bytes as f64)}</td>
                                            <td class="num dim">{format!("{:.1}%", p.mem_pct)}</td>
                                        </tr>
                                    }
                                }).collect_view()
                            }}
                        </tbody>
                    </table>
                </div>
            </div>

            // ---------------------------------------------------------------- CPU
            <div class="page detail c-cpu" class:active=move || page.get() == Page::Cpu>
                {head("CPU", move || snap.get().map(|s| s.cpu.brand).unwrap_or_default())}
                {axis("% utilization", || "100%".to_string())}
                {move || plot(hist_cpu.get(), vec![], 100.0)}
                {axis("60 seconds", || "0".to_string())}
                {move || snap.get().map(|s| view! {
                    <div class="facts">
                        {fact("Utilization", format!("{:.0}%", s.cpu.load))}
                        {fact("Speed", format!("{:.2} GHz", s.cpu.speed_mhz as f64 / 1000.0))}
                        {fact("Processes", s.proc_count.to_string())}
                        {fact("Up time", fmt_uptime(s.uptime))}
                    </div>
                    <div class="kvs">
                        {kv("Cores", s.cpu.physical_cores.to_string())}
                        {kv("Logical processors", s.cpu.logical_cores.to_string())}
                        {kv("Vendor", s.cpu.vendor.clone())}
                        {kv("Temperature", s.temp.map(|t| format!("{t:.0} °C")).unwrap_or_else(|| "n/a".into()))}
                        {kv("Host", s.hostname.clone())}
                        {kv("System", s.os.clone())}
                    </div>
                    <div class="sect">"Logical processors"</div>
                    <div class="cores">
                        {s.cpu.per_core.iter().enumerate().map(|(i, l)| view! {
                            <div class="core"><span>{i}</span>{bar(*l)}<span class="num">{format!("{l:.0}%")}</span></div>
                        }).collect_view()}
                    </div>
                })}
            </div>

            // ------------------------------------------------------------- Memory
            <div class="page detail c-mem" class:active=move || page.get() == Page::Mem>
                {head("Memory", move || snap.get().map(|s| fmt_bytes(s.mem.total as f64)).unwrap_or_default())}
                {axis("memory in use", move || snap.get().map(|s| fmt_bytes(s.mem.total as f64)).unwrap_or_default())}
                {move || plot(hist_mem.get(), vec![], 100.0)}
                {axis("60 seconds", || "0".to_string())}
                {move || snap.get().map(|s| view! {
                    <div class="facts">
                        {fact("In use", fmt_bytes(s.mem.used as f64))}
                        {fact("Available", fmt_bytes(s.mem.available as f64))}
                        {fact("Usage", format!("{:.0}%", pct_of(s.mem.used, s.mem.total)))}
                        {fact("Swap", format!("{} / {}", fmt_bytes(s.mem.swap_used as f64), fmt_bytes(s.mem.swap_total as f64)))}
                    </div>
                    <div class="sect">"Swap"</div>
                    {bar(pct_of(s.mem.swap_used, s.mem.swap_total))}
                })}
            </div>

            // --------------------------------------------------------------- Disk
            <div class="page detail c-disk" class:active=move || page.get() == Page::Disk>
                {head("Disk", move || cur_drive().map(|d| if d.model.is_empty() { d.name } else { d.model }).unwrap_or_default())}
                <div class="tabs">
                    {move || snap.get().map(|s| s.drives.iter().enumerate().map(|(i, d)| {
                        let n = d.name.clone();
                        view! { <span class="tab" class:sel=move || drive.get() == i on:click=move |_| drive.set(i)>{n}</span> }
                    }).collect_view())}
                </div>
                {axis("active time", || "100%".to_string())}
                {move || {
                    let name = cur_drive().map(|d| d.name).unwrap_or_default();
                    plot(hist_disk.get().get(&name).cloned().unwrap_or_default(), vec![], 100.0)
                }}
                {axis("60 seconds", || "0".to_string())}
                {axis("disk transfer rate (read solid, write faint)", move || {
                    let name = cur_drive().map(|d| d.name).unwrap_or_default();
                    let r = hist_dr.get().get(&name).cloned().unwrap_or_default();
                    let w = hist_dw.get().get(&name).cloned().unwrap_or_default();
                    fmt_rate(peak(&r, &w) as f64)
                })}
                {move || {
                    let name = cur_drive().map(|d| d.name).unwrap_or_default();
                    let r = hist_dr.get().get(&name).cloned().unwrap_or_default();
                    let w = hist_dw.get().get(&name).cloned().unwrap_or_default();
                    let max = peak(&r, &w);
                    plot(r, w, max)
                }}
                {axis("60 seconds", || "0".to_string())}
                {move || cur_drive().map(|d| {
                    let pct = pct_of(d.used, d.fs_total);
                    view! {
                        <div class="facts">
                            {fact("Active time", format!("{:.0}%", d.active_pct))}
                            {fact("Avg response time", format!("{:.1} ms", d.resp_ms))}
                            {fact("Read speed", fmt_rate(d.read_sec))}
                            {fact("Write speed", fmt_rate(d.write_sec))}
                        </div>
                        <div class="sect">{format!("Space usage - {pct:.0}% used")}</div>
                        <div class="facts">
                            {fact("Used", fmt_bytes(d.used as f64))}
                            {fact("Free", fmt_bytes(d.free as f64))}
                            {fact("Formatted", fmt_bytes(d.fs_total as f64))}
                            {fact("Capacity", fmt_bytes(d.size as f64))}
                        </div>
                        <div class="usage">{bar(pct)}</div>
                        <div class="kvs">{kv("Type", d.kind.clone())}{kv("Device", format!("/dev/{}", d.name))}</div>
                    }
                })}
                <div class="sect">"Partitions"</div>
                <table class="fs">
                    <thead><tr>
                        <th>"Mount"</th><th>"Type"</th><th class="num">"Used"</th><th class="num">"Free"</th>
                        <th class="num">"Size"</th><th class="num">"Use"</th><th class="barcol"></th>
                    </tr></thead>
                    <tbody>
                        {move || snap.get().map(|s| {
                            let name = cur_drive().map(|d| d.name).unwrap_or_default();
                            let mapped = s.filesystems.iter().any(|f| !f.drive.is_empty());
                            s.filesystems.iter().filter(|f| !mapped || f.drive == name).map(|f| view! {
                                <tr>
                                    <td>{f.mount.clone()}</td>
                                    <td class="dim">{f.fs.clone()}</td>
                                    <td class="num">{fmt_bytes(f.used as f64)}</td>
                                    <td class="num">{fmt_bytes(f.free as f64)}</td>
                                    <td class="num">{fmt_bytes(f.size as f64)}</td>
                                    <td class="num">{format!("{:.0}%", f.use_pct)}</td>
                                    <td class="barcol">{bar(f.use_pct)}</td>
                                </tr>
                            }).collect_view()
                        })}
                    </tbody>
                </table>
            </div>

            // ---------------------------------------------------------------- GPU
            <div class="page detail c-gpu" class:active=move || page.get() == Page::Gpu>
                {head("GPU", move || gpu.get().map(|g| g.model).unwrap_or_default())}
                {move || match gpu.get() {
                    Some(g) if !g.available => view! {
                        <div class="note">{format!("No GPU data: {}", g.error.unwrap_or_else(|| "offline".into()))}</div>
                    }.into_any(),
                    _ => view! {
                        <div>
                            {axis("% utilization", || "100%".to_string())}
                            {plot(hist_gpu.get(), vec![], 100.0)}
                            {axis("60 seconds", || "0".to_string())}
                        </div>
                    }.into_any(),
                }}
                {move || gpu.get().filter(|g| g.available).map(|g| view! {
                    <div class="facts">
                        {fact("Utilization", format!("{:.0}%", g.gfx))}
                        {fact("VRAM", format!("{:.0} / {:.0} MB", g.vram_used_mb, g.vram_total_mb))}
                        {fact("Memory clock", format!("{:.2} GHz", g.mclk_ghz))}
                        {fact("Shader clock", format!("{:.2} GHz", g.sclk_ghz))}
                    </div>
                    <div class="kvs">
                        {kv("Vendor", g.vendor.clone())}
                        {kv("Bus", g.bus.clone())}
                        {kv("Driver", g.driver.clone())}
                        {g.temp.map(|t| kv("Temperature", format!("{t:.0} °C")))}
                        {g.power_w.map(|w| kv("Power draw", format!("{w:.0} W")))}
                    </div>
                    <div class="sect">"Utilization breakdown"</div>
                    <div class="cores wide">
                        {g.blocks.iter().map(|(n, v)| view! {
                                <div class="core"><span>{n.clone()}</span>{bar(*v)}<span class="num">{format!("{v:.0}%")}</span></div>
                            })
                            .collect_view()}
                    </div>
                })}
            </div>

            // ------------------------------------------------------------ Network
            <div class="page detail c-net" class:active=move || page.get() == Page::Net>
                {head("Network", move || snap.get().and_then(|s| s.net).map(|n| n.iface).unwrap_or_default())}
                {axis("throughput (receive solid, send faint)", move || "".to_string())}
                {move || {
                    let rx = hist_rx.get();
                    let tx = hist_tx.get();
                    let max = rx.iter().chain(tx.iter()).cloned().fold(65_536.0_f32, f32::max);
                    plot(rx, tx, max)
                }}
                {axis("60 seconds", || "0".to_string())}
                {move || snap.get().and_then(|s| s.net).map(|n| view! {
                    <div class="facts">
                        {fact("Receive", fmt_rate(n.rx_sec))}
                        {fact("Send", fmt_rate(n.tx_sec))}
                        {fact("Received total", fmt_bytes(n.rx_bytes as f64))}
                        {fact("Sent total", fmt_bytes(n.tx_bytes as f64))}
                    </div>
                })}
                <div class="sect">"Interfaces"</div>
                <table class="fs">
                    <thead><tr><th>"Name"</th><th>"State"</th><th>"Speed"</th><th>"MAC"</th><th>"Address"</th></tr></thead>
                    <tbody>
                        {move || snap.get().map(|s| s.ifaces.iter().map(|i| view! {
                            <tr>
                                <td>{i.name.clone()}</td>
                                <td class=if i.state == "up" { "ok" } else { "dim" }>{i.state.clone()}</td>
                                <td class="dim">{i.speed_mbps.map(|s| format!("{s} Mbps")).unwrap_or_else(|| "-".into())}</td>
                                <td class="dim">{i.mac.clone()}</td>
                                <td>{if i.ips.is_empty() { "-".to_string() } else { i.ips.join("  ") }}</td>
                            </tr>
                        }).collect_view())}
                    </tbody>
                </table>
            </div>

            // -------------------------------------------------------------- About
            <div class="page detail" class:active=move || page.get() == Page::About>
                {head("About", || String::new())}
                <p class="prose">
                    "MuliOS Task Manager 1.0.3" <br />
                    "System monitor for Linux. Rust, Tauri, Leptos." <br /><br />
                    "For bug reports, check the local development repository."
                </p>
            </div>
        </div>

        {move || kill_target.get().map(|(pid, name)| view! {
            <div class="overlay">
                <div class="dialog">
                    <div class="dtitle">"End task"</div>
                    <p>{format!("End {name} (PID {pid})? Unsaved data in it will be lost.")}</p>
                    <div class="dbtns">
                        <button on:click=move |_| kill_target.set(None)>"Cancel"</button>
                        <button class="danger" on:click=confirm_kill>"End task"</button>
                    </div>
                </div>
            </div>
        })}
    }
}

fn main() {
    mount_to_body(App);
}
