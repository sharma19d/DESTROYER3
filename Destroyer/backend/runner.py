# backend/runner.py
"""
backend/runner.py

A single, cross-platform engine for Destroyer. Detects the OS and uses the
correct native commands for data destruction on Linux and Windows.
"""

import os
import re
import time
import json
import shlex
import shutil
import subprocess
import platform
import hashlib
import socket
from datetime import datetime
# --- MODIFIED: Replaced the old logger setup with an import ---
from utils.logger import logger

# --- Constants ---
TOOL_VERSION = "1.2.0" # Version bump for cross-platform support
# Use paths relative to this file, making it 100% portable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

class RunnerError(Exception):
    pass

class WipeRunner:
    def __init__(self, dry_run=True):
        self.dry_run = bool(dry_run)
        self.is_linux = platform.system().lower() == "linux"
        self.log_dir = LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)

    def _get_device_path(self, device_info):
        if isinstance(device_info, dict): return device_info.get("path", "")
        if isinstance(device_info, str): return device_info
        return ""

    def _run_command(self, cmd: str, timeout: int = 7200):
        logger.info(f"Running: {cmd}")
        try:
            # On Windows, shell=True is often needed for commands like 'format'
            use_shell = not self.is_linux
            proc = subprocess.run(cmd, capture_output=True, text=True, shell=use_shell, timeout=timeout)
            return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as e:
            return {"cmd": cmd, "returncode": -1, "stdout": "", "stderr": f"Error: {e}"}

    def _simulate_command(self, cmd: str):
        logger.info(f"[SIMULATE] {cmd}")
        time.sleep(0.5)
        return {"cmd": cmd, "returncode": 0, "stdout": f"[SIMULATED] {cmd}", "stderr": ""}

    def _prepare_commands(self, device_path: str, mode: str):
        mode = mode.lower()
        # --- OS DETECTION LOGIC ---
        if self.is_linux:
            # --- Linux Toolbox ---
            devtype = "nvme" if "nvme" in device_path else "ata"
            if mode == "quick": return [f"shred -n 1 -z {shlex.quote(device_path)}"]
            if mode == "paranoid": return [f"shred -n 3 -z {shlex.quote(device_path)}"]
            if mode == "crypto":
                if devtype == "nvme": return [f"nvme format {shlex.quote(device_path)} --ses=1"]
                else: return [f"hdparm --user-master u --security-set-pass p {shlex.quote(device_path)}", f"hdparm --user-master u --security-erase p {shlex.quote(device_path)}"]
            if mode == "forensic":
                if devtype == "nvme": return [f"nvme format {shlex.quote(device_path)} --ses=2"]
                else: return [f"hdparm --dco-restore {shlex.quote(device_path)}", f"hdparm -N p`hdparm -N {shlex.quote(device_path)} | grep 'max' | cut -d/ -f2` {shlex.quote(device_path)}", f"hdparm --user-master u --security-set-pass p {shlex.quote(device_path)}", f"hdparm --user-master u --security-erase-enhanced p {shlex.quote(device_path)}"]
        else:
            # --- Windows Toolbox ---
            drive_letter = device_path.strip()[:2]
            if mode == "quick": return [f'format {drive_letter} /fs:NTFS /y /p:0']
            if mode == "paranoid": return [f'format {drive_letter} /fs:NTFS /y /p:2']
            if mode in ["crypto", "forensic"]:
                logger.warning("Crypto/Forensic mode on Windows defaults to the most secure software wipe (3-pass).")
                return [f'format {drive_letter} /fs:NTFS /y /p:2']
        raise RunnerError(f"Unknown mode or unsupported OS: {mode}")

    def run_wipe(self, device_info: dict, mode: str = "quick", execute: bool = False):
        device_path = self._get_device_path(device_info)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = re.sub(r'[^\w\-_.]', '_', device_path)
        log_file = os.path.join(self.log_dir, f"wipe_{safe_name}_{timestamp}.log")

        try:
            commands = self._prepare_commands(device_path, mode)
        except RunnerError as e:
            return {"success": False, "error": str(e), "device_details": device_info, "wipe_mode": mode}

        results, overall_success = [], True
        for cmd in commands:
            res = self._simulate_command(cmd) if self.dry_run or not execute else self._run_command(cmd)
            results.append(res)
            if res["returncode"] != 0:
                overall_success = False
                break

        system_info = {"hostname": socket.gethostname(), "os": platform.platform()}
        log_data = {
            "device_details": device_info, "wipe_mode": mode, "timestamp_utc": timestamp,
            "success": overall_success, "system_info": system_info, "tool_version": TOOL_VERSION,
            "results": results, "log_file": log_file
        }
        with open(log_file, "w") as f: json.dump(log_data, f, indent=4, default=str)

        log_hash = "N/A"
        if overall_success:
            hasher = hashlib.sha256()
            with open(log_file, 'rb') as f: hasher.update(f.read())
            log_hash = hasher.hexdigest()
        
        return {**log_data, "verification": {"log_hash_sha256": log_hash}}