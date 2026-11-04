use std::env;
use std::net::SocketAddr;
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde_json::{Value, json};
use sysinfo::{Pid, System};
use tower_http::services::ServeDir;

type SharedSystem = Arc<Mutex<System>>;

#[tokio::main]
async fn main() -> ExitCode {
    if env::args().any(|arg| arg == "--version" || arg == "-V") {
        println!("mulios-taskmanager {}", env!("CARGO_PKG_VERSION"));
        return ExitCode::SUCCESS;
    }

    let port = match env::var("MULIOS_TASKMANAGER_PORT") {
        Ok(value) => match value.parse::<u16>() {
            Ok(port) => port,
            Err(error) => {
                eprintln!("mulios-taskmanager: invalid port: {error}");
                return ExitCode::FAILURE;
            }
        },
        Err(_) => 4700,
    };

    let system = Arc::new(Mutex::new(System::new_all()));
    let app_dir = env::var("MULIOS_TASKMANAGER_DIR")
        .unwrap_or_else(|_| "/opt/taskmanager".to_owned());

    let app = Router::new()
        .route("/api/system", get(system_info))
        .route("/api/processes", get(process_list))
        .route("/api/gpu", get(gpu_info))
        .route("/api/kill", post(kill_process))
        .with_state(system)
        .fallback_service(ServeDir::new(app_dir));

    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = match tokio::net::TcpListener::bind(address).await {
        Ok(listener) => listener,
        Err(error) => {
            eprintln!("mulios-taskmanager: cannot bind {address}: {error}");
            return ExitCode::FAILURE;
        }
    };

    println!("MuliOS Task Manager listening at http://{address}");
    match axum::serve(listener, app).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("mulios-taskmanager: server error: {error}");
            ExitCode::FAILURE
        }
    }
}

async fn system_info(State(shared): State<SharedSystem>) -> Json<Value> {
    let mut system = match shared.lock() {
        Ok(system) => system,
        Err(_) => return Json(json!({"error": "system monitor lock is poisoned"})),
    };
    system.refresh_all();

    let cpus = system.cpus();
    let cpu_brand = cpus.first().map(|cpu| cpu.brand()).unwrap_or("Unknown CPU");
    let cpu_vendor = cpus.first().map(|cpu| cpu.vendor_id()).unwrap_or("Unknown");
    let cpu_speed = cpus.first().map(|cpu| cpu.frequency()).unwrap_or(0);
    let cpu_count = cpus.len();
    let total_memory = system.total_memory();
    let used_memory = system.used_memory();
    let available_memory = system.available_memory();

    let process_count = system.processes().len();
    let os_name = System::name().unwrap_or_else(|| "Linux".to_owned());
    let os_version = System::os_version().unwrap_or_default();
    let host_name = System::host_name().unwrap_or_default();

    Json(json!({
        "cpuInfo": {
            "manufacturer": cpu_vendor,
            "brand": cpu_brand,
            "vendor": cpu_vendor,
            "family": "",
            "model": "",
            "socket": "1",
            "speed": cpu_speed as f64 / 1000.0,
            "speedMax": cpu_speed as f64 / 1000.0,
            "cores": cpu_count,
            "physicalCores": System::physical_core_count().unwrap_or(cpu_count),
            "cache": {"l1": 0, "l2": 0, "l3": 0}
        },
        "cpu": {
            "currentLoad": system.global_cpu_usage(),
            "cpus": cpus.iter().map(|cpu| json!({
                "load": cpu.cpu_usage(),
                "speed": cpu.frequency()
            })).collect::<Vec<_>>()
        },
        "mem": {
            "active": used_memory,
            "total": total_memory,
            "available": available_memory,
            "buffcache": 0,
            "swapused": system.used_swap(),
            "swaptotal": system.total_swap()
        },
        "memLayout": [],
        "osInfo": {
            "distro": os_name,
            "release": os_version,
            "hostname": host_name,
            "platform": "linux",
            "arch": env::consts::ARCH
        },
        "diskLayout": [],
        "disks": [],
        "netIfaces": [],
        "disksIO": {"rIO_sec": 0, "wIO_sec": 0, "ms": 1000},
        "net": null,
        "temp": null,
        "procCount": process_count,
        "uptime": System::uptime()
    }))
}

async fn process_list(State(shared): State<SharedSystem>) -> Json<Value> {
    let mut system = match shared.lock() {
        Ok(system) => system,
        Err(_) => return Json(json!({"list": [], "error": "system monitor lock is poisoned"})),
    };
    system.refresh_all();

    let total_memory = system.total_memory().max(1) as f64;
    let mut list = system.processes().iter().map(|(pid, process)| {
        let command = process.cmd().iter()
            .map(|part| part.to_string_lossy().into_owned())
            .collect::<Vec<_>>()
            .join(" ");
        let memory_bytes = process.memory();
        json!({
            "pid": pid.as_u32(),
            "name": process.name().to_string_lossy(),
            "cpu": process.cpu_usage(),
            "mem": memory_bytes as f64 / total_memory * 100.0,
            "memRss": memory_bytes / 1024,
            "user": "unknown",
            "state": format!("{:?}", process.status()),
            "command": command
        })
    }).collect::<Vec<_>>();

    list.sort_by(|a, b| {
        let a_cpu = a.get("cpu").and_then(Value::as_f64).unwrap_or(0.0);
        let b_cpu = b.get("cpu").and_then(Value::as_f64).unwrap_or(0.0);
        b_cpu.total_cmp(&a_cpu)
    });

    Json(json!({"list": list}))
}

async fn gpu_info() -> Json<Value> {
    let mut gpu = json!({
        "vendor": "Unknown",
        "model": "Unknown GPU",
        "bus": null,
        "vramDetected": null,
        "driverVersion": null,
        "gfx": 0,
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
        "vramUsed": 0,
        "vramTotal": 0,
        "mclk": 0,
        "sclk": 0
    });

    if let Ok(output) = std::process::Command::new("sudo")
        .args(["-n", "radeontop", "-d", "-", "-l", "1"])
        .output()
    {
        let report = String::from_utf8_lossy(&output.stdout);
        for (field, needle) in [
            ("gfx", "gpu "),
            ("event", "ee "),
            ("vgt", "vgt "),
            ("ta", "ta "),
            ("sx", "sx "),
            ("sci", "sh "),
            ("si", "spi "),
            ("sc", "sc "),
            ("pa", "pa "),
            ("db", "db "),
            ("cb", "cb ")
        ] {
            if let Some(value) = parse_percent(&report, needle) {
                gpu[field] = json!(value);
            }
        }
        if let Some(value) = parse_number_before(&report, "vram ", "mb") {
            gpu["vramUsed"] = json!(value);
        }
        if let Some(value) = parse_number_before(&report, "mclk ", "ghz") {
            gpu["mclk"] = json!(value);
        }
        if let Some(value) = parse_number_before(&report, "sclk ", "ghz") {
            gpu["sclk"] = json!(value);
        }
    }

    Json(gpu)
}

async fn kill_process(
    State(shared): State<SharedSystem>,
    Json(payload): Json<Value>,
) -> (StatusCode, Json<Value>) {
    let Some(pid) = payload.get("pid").and_then(Value::as_u64) else {
        return (StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": "A numeric PID is required"})));
    };
    let Ok(pid) = u32::try_from(pid) else {
        return (StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": "PID is out of range"})));
    };

    let mut system = match shared.lock() {
        Ok(system) => system,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"success": false, "error": "system monitor lock is poisoned"}))),
    };
    system.refresh_processes(sysinfo::ProcessesToUpdate::Some(&[Pid::from_u32(pid)]), true);
    let Some(process) = system.process(Pid::from_u32(pid)) else {
        return (StatusCode::NOT_FOUND, Json(json!({"success": false, "error": "Process not found"})));
    };

    match process.kill() {
        true => (StatusCode::OK, Json(json!({"success": true, "error": null}))),
        false => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"success": false, "error": "The operating system refused to terminate the process"}))),
    }
}

fn parse_percent(report: &str, needle: &str) -> Option<f64> {
    let start = report.find(needle)? + needle.len();
    let value = report[start..].split('%').next()?.trim();
    value.parse().ok()
}

fn parse_number_before(report: &str, needle: &str, suffix: &str) -> Option<f64> {
    let start = report.find(needle)? + needle.len();
    let tail = &report[start..];
    let end = tail.find(suffix)?;
    tail[..end].split_whitespace().last()?.parse().ok()
}
