# backend/device_detect.py
"""
backend/device_detect.py

Cross-platform device detection for Destroyer.
- On Windows: uses psutil to list drives.
- On Linux: uses lsblk to list block devices, including model and serial.
--- MODIFIED: Standardized the output dictionary to prevent KeyErrors. ---
"""

import platform
import psutil
import subprocess
import json
from utils.logger import logger

def _get_linux_device_details(device_name):
    """Helper to get model and serial for a specific Linux device."""
    try:
        # -b for bytes, -J for JSON, -o for specific columns
        cmd = ["lsblk", "-b", "-J", "-o", "MODEL,SERIAL", f"/dev/{device_name}"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        # The output is a list, we need the first item
        details = data.get("blockdevices", [{}])[0]
        return {
            "model": details.get("model", "N/A"),
            "serial": details.get("serial", "N/A"),
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError, KeyError):
        # If the command fails or parsing fails, return defaults
        return {"model": "N/A", "serial": "N/A"}

def list_devices():
    """
    Detects connected storage devices with hardware details.
    Returns a list of dicts: {name, path, size, mountpoint, model, serial}
    """
    system = platform.system().lower()
    devices = []

    if system == "windows":
        # psutil.disk_partitions(all=False) lists only physical drives on some systems
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                # --- MODIFIED: Ensure consistent dictionary structure ---
                devices.append({
                    "name": part.device,
                    "path": part.device, # The 'path' key is guaranteed
                    "size": f"{usage.total // (1024**3)}G",
                    "mountpoint": part.mountpoint,
                    "model": "N/A (Windows)",
                    "serial": "N/A (Windows)",
                })
            except Exception as e:
                logger.error(f"Error detecting device {part.device}: {e}")

    elif system == "linux":
        try:
            # -b for bytes, -J for JSON, -d for no slaves (partitions), -o for columns
            result = subprocess.run(
                ["lsblk", "-b", "-J", "-d", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
            )
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                # We already filter for disks with '-d', but an extra check is safe
                if dev.get("type") == "disk":
                    details = _get_linux_device_details(dev["name"])
                    # --- MODIFIED: Ensure consistent dictionary structure & user-friendly size ---
                    size_in_bytes = int(dev.get("size", 0))
                    size_gb = f"{size_in_bytes // (1024**3)}G"
                    
                    devices.append({
                        "name": dev["name"],
                        "path": f"/dev/{dev['name']}", # The 'path' key is guaranteed
                        "size": size_gb,
                        "mountpoint": dev.get("mountpoint") or "N/A", # Use 'N/A' if mountpoint is None
                        "model": details["model"],
                        "serial": details["serial"]
                    })
        except Exception as e:
            # Using logger for consistency
            logger.error(f"Error detecting devices on Linux: {e}")

    else:
        logger.error(f"Unsupported OS: {system}")

    return devices

# Quick test when running this file directly
if __name__ == "__main__":
    print("=== Device Detection (Enhanced) ===")
    detected_devices = list_devices()
    if not detected_devices:
        print("No devices found.")
    else:
        for d in detected_devices:
            # Using .get() for safe printing during tests
            print(f"Path: {d.get('path')} | Size: {d.get('size')} | Model: {d.get('model')} | Serial: {d.get('serial')}")