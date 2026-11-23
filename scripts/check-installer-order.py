#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])
mode = sys.argv[2]
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)
run = next((node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "run"), None)
if run is None:
    raise SystemExit("run() method not found")

calls = []
for node in ast.walk(run):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
            calls.append((node.func.attr, node.lineno))

if mode == "install":
    names = ("install_kernel_image", "copy_system", "configure_kernel")
    positions = {name: next((line for call, line in calls if call == name), None)
                 for name in names}
    if any(value is None for value in positions.values()) or not (
        positions[names[0]] < positions[names[1]] < positions[names[2]]
    ):
        raise SystemExit(f"Incorrect install order: {positions}")
    method = next((node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == names[0]), None)
    if method is None:
        raise SystemExit("install_kernel_image() method not found")
    method_source = ast.get_source_segment(source, method) or ""
    if "kernel_destination.is_file()" not in method_source or "refusing to copy the live airootfs" not in method_source:
        raise SystemExit("Kernel image must be verified before the airootfs copy can proceed")
    print("Kernel image installation is ordered first and verified before airootfs copy.")
elif mode == "profile":
    names = ("configure_mupdate", "generate_initramfs", "configure_bootloader")
    positions = {name: next((line for call, line in calls if call == name), None)
                 for name in names}
    if any(value is None for value in positions.values()) or not (
        positions[names[0]] < positions[names[1]] < positions[names[2]]
    ):
        raise SystemExit(f"Profile kernel/initramfs/GRUB order is invalid: {positions}")
    print("Profile installation precedes initramfs generation and GRUB generation.")
else:
    raise SystemExit(f"Unknown check mode: {mode}")
