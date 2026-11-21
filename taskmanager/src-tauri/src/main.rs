#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod collect;

use std::sync::{Arc, Mutex};

use collect::{spawn_gpu_poller, Collector};
use shared::{GpuInfo, ProcInfo, SystemSnapshot};
use tauri::State;

struct AppState {
    collector: Mutex<Collector>,
    gpu: Arc<Mutex<GpuInfo>>,
}

#[tauri::command]
async fn get_system(state: State<'_, AppState>) -> Result<SystemSnapshot, String> {
    let mut c = state.collector.lock().map_err(|e| e.to_string())?;
    Ok(c.snapshot())
}

#[tauri::command]
async fn get_processes(state: State<'_, AppState>) -> Result<Vec<ProcInfo>, String> {
    let mut c = state.collector.lock().map_err(|e| e.to_string())?;
    Ok(c.processes())
}

#[tauri::command]
async fn get_gpu(state: State<'_, AppState>) -> Result<GpuInfo, String> {
    Ok(state.gpu.lock().map_err(|e| e.to_string())?.clone())
}

#[tauri::command]
async fn kill_process(state: State<'_, AppState>, pid: u32) -> Result<(), String> {
    let mut c = state.collector.lock().map_err(|e| e.to_string())?;
    c.kill(pid)
}

fn main() {
    let gpu = Arc::new(Mutex::new(GpuInfo::default()));
    spawn_gpu_poller(gpu.clone());

    tauri::Builder::default()
        .manage(AppState {
            collector: Mutex::new(Collector::new()),
            gpu,
        })
        .invoke_handler(tauri::generate_handler![
            get_system,
            get_processes,
            get_gpu,
            kill_process
        ])
        .run(tauri::generate_context!())
        .expect("error while running MuliOS Task Manager");
}
