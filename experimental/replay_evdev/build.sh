#!/usr/bin/env bash

# Fail on error, verbose output
set -exo pipefail

# Figure out which ABI and SDK the device has
abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
sdk=$(adb shell getprop ro.build.version.sdk | tr -d '\r')

# Build project
cmake -DCMAKE_TOOLCHAIN_FILE=$ANDROID_HOME/ndk-bundle/build/cmake/android.toolchain.cmake \
      -DANDROID_ABI=x86 -DANDROID_NATIVE_API_LEVEL=16 \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=yes \
      -H. -Bbuild
make -Cbuild

# Upload the binary
adb push build/replay_evdev /data/local/tmp/

# Run!
# adb shell /data/local/tmp/$bin "$@"
