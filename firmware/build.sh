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

# Copy the SDK import helper into the project directory (required by CMake)
cp "$PICO_SDK_PATH/external/pico_sdk_import.cmake" "$(dirname "$0")/pico_sdk_import.cmake"

BUILD_DIR="$(dirname "$0")/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)"

echo ""
echo "Build complete. Flash firmware/build/redwing.uf2 to the RP2040."
echo "Hold BOOTSEL while plugging in USB, then drag-and-drop the .uf2 file."
