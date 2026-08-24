#!/bin/bash
# Build the Redwing RP2040 firmware.
# Requires the Pico SDK to be installed and PICO_SDK_PATH set.
#
# If you used the Raspberry Pi Pico VS Code extension to install the SDK,
# PICO_SDK_PATH is set automatically in your VS Code terminal.

set -e

if [ -z "$PICO_SDK_PATH" ]; then
    echo "ERROR: PICO_SDK_PATH is not set."
    echo "Set it to the path where you installed the Pico SDK, e.g.:"
    echo "  export PICO_SDK_PATH=\$HOME/.pico-sdk/sdk/2.1.0"
    exit 1
fi

# Resolved once, up front, as an absolute path — used again after we cd into
# BUILD_DIR below, where a re-evaluated "$(dirname "$0")" would otherwise
# resolve relative to the wrong (new) working directory.
FIRMWARE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Copy the SDK import helper into the project directory (required by CMake)
cp "$PICO_SDK_PATH/external/pico_sdk_import.cmake" "$FIRMWARE_DIR/pico_sdk_import.cmake"

BUILD_DIR="$FIRMWARE_DIR/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)"

# Copy to a stable, git-tracked path (firmware/build/ itself is gitignored —
# it's a full CMake work directory). Committing this one file is what lets a
# `git pull` on a Pi update its firmware without needing the Pico SDK/toolchain
# installed there — see the dashboard's Firmware tab / README.
cp redwing.uf2 "$FIRMWARE_DIR/redwing.uf2"

echo ""
echo "Build complete: firmware/redwing.uf2"
echo "Commit and push this file to publish the build to every Pi's next 'git pull'."
echo "To flash manually instead: hold BOOTSEL while plugging in USB, then drag-and-drop the .uf2 file."
