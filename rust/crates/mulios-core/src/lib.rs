//! Shared, dependency-free system information primitives for MuliOS.
//!
//! These interfaces are read-only, require no root privileges, and are Linux-specific.

use std::collections::BTreeMap;
use std::fs;
use std::io;

/// Distribution metadata parsed from /etc/os-release.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct OsRelease {
    pub name: Option<String>,
    pub pretty_name: Option<String>,
    pub id: Option<String>,
    pub version_id: Option<String>,
}

/// Memory totals from /proc/meminfo, expressed in bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MemoryInfo {
    pub total_bytes: u64,
    pub available_bytes: Option<u64>,
}

/// Read and parse operating system release metadata.
pub fn os_release() -> io::Result<OsRelease> {
    let contents = fs::read_to_string("/etc/os-release")?;
    let values = parse_os_release(&contents);
    Ok(OsRelease {
        name: values.get("NAME").cloned(),
        pretty_name: values.get("PRETTY_NAME").cloned(),
        id: values.get("ID").cloned(),
        version_id: values.get("VERSION_ID").cloned(),
    })
}

/// Parse os-release key/value lines, including simple single/double quoting.
pub fn parse_os_release(contents: &str) -> BTreeMap<String, String> {
    contents
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }
            let (key, value) = line.split_once('=')?;
            let key = key.trim();
            if key.is_empty()
                || !key
                    .bytes()
                    .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_')
            {
                return None;
            }
            let value = value.trim();
            let value = if value.len() >= 2 {
                let first = value.as_bytes()[0];
                let last = value.as_bytes()[value.len() - 1];
                if (first == b'"' && last == b'"') || (first == 39 && last == 39) {
                    &value[1..value.len() - 1]
                } else {
                    value
                }
            } else {
                value
            };
            Some((key.to_owned(), value.to_owned()))
        })
        .collect()
}

/// Read physical memory totals from /proc/meminfo.
pub fn memory_info() -> io::Result<MemoryInfo> {
    let contents = fs::read_to_string("/proc/meminfo")?;
    let values: BTreeMap<&str, u64> = contents
        .lines()
        .filter_map(|line| {
            let (key, rest) = line.split_once(':')?;
            let amount = rest.split_whitespace().next()?.parse().ok()?;
            Some((key, amount))
        })
        .collect();
    let total_kib = *values
        .get("MemTotal")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "MemTotal missing"))?;
    let available_kib = values.get("MemAvailable").copied();
    Ok(MemoryInfo {
        total_bytes: total_kib.saturating_mul(1024),
        available_bytes: available_kib.map(|value| value.saturating_mul(1024)),
    })
}

/// Read system uptime in seconds from /proc/uptime.
pub fn uptime_seconds() -> io::Result<f64> {
    let contents = fs::read_to_string("/proc/uptime")?;
    let first = contents
        .split_whitespace()
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "uptime value missing"))?;
    first
        .parse()
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_quoted_os_release_values_and_ignores_comments() {
        let parsed = parse_os_release(
            "# comment\\nNAME=Arch\\nPRETTY_NAME=\\\"MuliOS Arch 1.0\\\"\\nID='mulios'\\n",
        );
        assert_eq!(parsed.get("NAME").map(String::as_str), Some("Arch"));
        assert_eq!(
            parsed.get("PRETTY_NAME").map(String::as_str),
            Some("MuliOS Arch 1.0")
        );
        assert_eq!(parsed.get("ID").map(String::as_str), Some("mulios"));
        assert_eq!(parsed.len(), 3);
    }

    #[test]
    fn rejects_invalid_keys_and_lines_without_equals() {
        let parsed =
            parse_os_release("lower=value\\nNOT A KEY=value\\nBROKEN\\nGOOD=yes\\n");
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed.get("GOOD").map(String::as_str), Some("yes"));
    }
}
