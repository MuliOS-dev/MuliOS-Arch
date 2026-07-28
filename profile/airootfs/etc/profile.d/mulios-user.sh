#!/bin/bash

if ! id mulios >/dev/null 2>&1; then
    useradd -m -G wheel,audio,video,network mulios
    echo "mulios:mulios" | chpasswd
fi