use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, ExitCode, Stdio};
use std::thread;
use std::time::Duration;

const VERSION: &str = env!("CARGO_PKG_VERSION");
const WALLPAPER: &str = "/usr/share/backgrounds/mulios/wallpaper.png";

fn main() -> ExitCode {
    let mut args = env::args().skip(1);
    match args.next().as_deref() {
        Some("version") | Some("--version") | Some("-V") => {
            println!("muliosctl {VERSION}");
            ExitCode::SUCCESS
        }
        Some("info") => print_info(),
        Some("wallpaper") => match args.next().as_deref() {
            Some("apply") => apply_wallpaper(),
            Some("autostart") => {
                thread::sleep(Duration::from_secs(3));
                apply_wallpaper()
            }
            _ => {
                eprintln!("Usage: muliosctl wallpaper <apply|autostart>");
                ExitCode::from(2)
            }
        },
        Some("help") | Some("--help") | Some("-h") | None => {
            print_help();
            ExitCode::SUCCESS
        }
        Some(command) => {
            eprintln!("muliosctl: unknown command '{command}'");
            print_help();
            ExitCode::from(2)
        }
    }
}

fn print_help() {
    println!(
        "muliosctl {VERSION}\nNative MuliOS system utility\n\nUsage:\n  muliosctl <command>\n\nCommands:\n  info                  Show operating system and memory information\n  wallpaper apply       Apply the MuliOS Plasma wallpaper\n  wallpaper autostart   Apply wallpaper after desktop startup\n  version               Show application version\n  help                  Show this help"
    );
}

fn print_info() -> ExitCode {
    match mulios_core::os_release() {
        Ok(os) => {
            println!(
                "Operating system: {}",
                os.pretty_name.or(os.name).unwrap_or_else(|| "Unknown".into())
            );
            println!(
                "Distribution ID: {}",
                os.id.unwrap_or_else(|| "unknown".into())
            );
            println!(
                "Version: {}",
                os.version_id.unwrap_or_else(|| "unknown".into())
            );
        }
        Err(error) => {
            eprintln!("muliosctl: unable to read /etc/os-release: {error}");
            return ExitCode::FAILURE;
        }
    }
    match mulios_core::memory_info() {
        Ok(memory) => {
            println!("Memory total: {}", format_bytes(memory.total_bytes));
            if let Some(available) = memory.available_bytes {
                println!("Memory available: {}", format_bytes(available));
            }
        }
        Err(error) => eprintln!("Memory information unavailable: {error}"),
    }
    match mulios_core::uptime_seconds() {
        Ok(seconds) => println!("Uptime: {}", format_duration(seconds)),
        Err(error) => eprintln!("Uptime unavailable: {error}"),
    }
    ExitCode::SUCCESS
}

fn apply_wallpaper() -> ExitCode {
    let wallpaper = PathBuf::from(WALLPAPER);
    if !wallpaper.is_file() {
        return ExitCode::SUCCESS;
    }

    let home = match env::var_os("HOME") {
        Some(home) => PathBuf::from(home),
        None => {
            eprintln!("muliosctl: HOME is not set; cannot create wallpaper marker");
            return ExitCode::FAILURE;
        }
    };
    let marker = home.join(".config/.mulios-wallpaper-applied");
    if let Some(parent) = marker.parent() {
        if let Err(error) = fs::create_dir_all(parent) {
            eprintln!("muliosctl: cannot create {}: {error}", parent.display());
            return ExitCode::FAILURE;
        }
    }

    if command_exists("plasma-apply-wallpaperimage") {
        for _ in 0..20 {
            let status = Command::new("plasma-apply-wallpaperimage")
                .arg(&wallpaper)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            if status.is_ok_and(|status| status.success()) {
                return write_wallpaper_marker(&marker);
            }
            thread::sleep(Duration::from_secs(1));
        }
    }

    let qdbus = ["qdbus6", "qdbus"]
        .into_iter()
        .find(|candidate| command_exists(candidate));
    if let Some(qdbus) = qdbus {
        let script = format!(
            "var desktopsList = desktops();\nfor (var i = 0; i < desktopsList.length; ++i) {{\n    var desktop = desktopsList[i];\n    desktop.wallpaperPlugin = \"org.kde.image\";\n    desktop.currentConfigGroup = [\"Wallpaper\", \"org.kde.image\", \"General\"];\n    desktop.writeConfig(\"Image\", \"file://{}\");\n}}",
            WALLPAPER
        );
        for _ in 0..10 {
            let status = Command::new(qdbus)
                .args([
                    "org.kde.plasmashell",
                    "/PlasmaShell",
                    "org.kde.PlasmaShell.evaluateScript",
                    &script,
                ])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            if status.is_ok_and(|status| status.success()) {
                return write_wallpaper_marker(&marker);
            }
            thread::sleep(Duration::from_secs(1));
        }
    }

    eprintln!("muliosctl: unable to apply wallpaper using Plasma's available interfaces");
    ExitCode::FAILURE
}

fn command_exists(command: &str) -> bool {
    env::split_paths(&env::var_os("PATH").unwrap_or_default())
        .any(|directory| directory.join(command).is_file())
}

fn write_wallpaper_marker(marker: &std::path::Path) -> ExitCode {
    match fs::write(marker, b"applied\n") {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("muliosctl: wallpaper applied, but marker could not be written: {error}");
            ExitCode::FAILURE
        }
    }
}

fn format_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KiB", "MiB", "GiB", "TiB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    format!("{value:.1} {}", UNITS[unit])
}

fn format_duration(seconds: f64) -> String {
    let total = seconds.max(0.0) as u64;
    let days = total / 86_400;
    let hours = (total % 86_400) / 3_600;
    let minutes = (total % 3_600) / 60;
    let secs = total % 60;
    if days > 0 {
        format!("{days}d {hours}h {minutes}m")
    } else if hours > 0 {
        format!("{hours}h {minutes}m {secs}s")
    } else {
        format!("{minutes}m {secs}s")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_binary_units() {
        assert_eq!(format_bytes(1024), "1.0 KiB");
        assert_eq!(format_bytes(1024 * 1024), "1.0 MiB");
    }

    #[test]
    fn formats_uptime() {
        assert_eq!(format_duration(61.0), "1m 1s");
        assert_eq!(format_duration(3_661.0), "1h 1m 1s");
        assert_eq!(format_duration(90_061.0), "1d 1h 1m");
    }
}
