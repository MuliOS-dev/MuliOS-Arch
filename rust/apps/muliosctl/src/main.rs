use std::process::ExitCode;

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some("version") | Some("--version") | Some("-V") => {
            println!("muliosctl {VERSION}");
            ExitCode::SUCCESS
        }
        Some("info") => print_info(),
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
        "muliosctl {VERSION}\nNative MuliOS system utility\n\nUsage:\n  muliosctl <command>\n\nCommands:\n  info       Show operating system and memory information\n  version    Show application version\n  help       Show this help"
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
