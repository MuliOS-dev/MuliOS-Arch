# Native MuliOS Task Manager backend

This is the Rust migration target for the current Task Manager's local HTTP
backend. It intentionally keeps the existing browser UI and API paths so the
backend can be evaluated without changing the desktop launcher.

## Build and run

From the repository root:

```sh
cargo build -p mulios-taskmanager
MULIOS_TASKMANAGER_DIR="$PWD/profile/airootfs/opt/taskmanager" \
  cargo run -p mulios-taskmanager
```

Open http://127.0.0.1:4700 in a browser. The server binds to loopback only.

Environment:

- `MULIOS_TASKMANAGER_PORT`: listening port (default: `4700`).
- `MULIOS_TASKMANAGER_DIR`: directory containing the existing HTML/CSS/JS
  assets (default: `/opt/taskmanager`).

## API compatibility

- `GET /api/system`
- `GET /api/processes`
- `GET /api/gpu`
- `POST /api/kill`

## Migration status

This backend is experimental and is staged separately from the production
Node.js backend. It already provides live CPU, memory, uptime, and process
information and a GPU telemetry probe through `radeontop`.

Disk inventory, disk I/O, network-interface details, DIMM layout, and complete
GPU identity/telemetry are not yet at parity with the existing implementation.
Do not switch the default launcher or remove Node.js until those fields are
implemented and the complete application passes QEMU testing.
