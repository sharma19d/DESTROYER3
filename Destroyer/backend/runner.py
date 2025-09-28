# backend/runner.py
"""
backend/runner.py

A single, cross-platform engine for Destroyer. Detects the OS and uses the
correct native commands for data destruction on Linux and Windows.

--- VERSION 2.0 REWRITE ---
This module has been completely redesigned to support a real-time UI.
- It now runs commands asynchronously, capturing live stdout/stderr.
- It parses command output to calculate a real-time progress percentage.
- It uses a callback function to report status and progress back to the API layer,
  making it decoupled and perfect for a separate UI thread.
"""

import os
import re
import time
import json
import shlex
import subprocess
import platform
import hashlib
import socket
from datetime import datetime
from utils.logger import logger

# --- Constants ---
TOOL_VERSION = "2.0.0" # Version bump for UI support
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

class RunnerError(Exception):
    """Custom exception for errors during the wipe process."""
    pass

class WipeRunner:
    """
    Manages the entire data destruction process, with real-time progress reporting.
    """
    def __init__(self, dry_run=False, status_callback=None):
        """
        Initializes the WipeRunner.

        Args:
            dry_run (bool): If True, simulates commands instead of executing them.
            status_callback (function): A function to call with progress updates.
                                        It should accept a dictionary, e.g.,
                                        callback({"status": "wiping", "progress": 10, "message": "Running shred..."})
        """
        self.dry_run = bool(dry_run)
        self.is_linux = platform.system().lower() == "linux"
        self.log_dir = LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        
        # The callback is the key to communication with the UI thread.
        self.status_callback = status_callback

    def _update_status(self, status, progress, message):
        """Helper function to safely call the status callback if it exists."""
        if self.status_callback:
            self.status_callback({
                "status": status,
                "progress": progress,
                "message": message
            })
        logger.info(f"[STATUS] {status} - {progress}%: {message}")

    def _get_device_path(self, device_info):
        """Safely extracts the device path from various input types."""
        if isinstance(device_info, dict):
            return device_info.get("path", "")
        if isinstance(device_info, str):
            return device_info
        return ""

    def _prepare_commands(self, device_path: str, mode: str):
        """
        Prepares a list of platform-specific shell commands for the wipe.
        This is where the core logic for choosing the right tool resides.
        """
        mode = mode.lower()
        if not device_path:
            raise RunnerError("Device path cannot be empty.")

        # --- OS-Specific Command Toolbox ---
        if self.is_linux:
            # On Linux, we use tools like shred, nvme-cli, and hdparm.
            devtype = "nvme" if "nvme" in device_path else "ata"
            # NOTE: We add '-v' to shred to get verbose progress output.
            if mode == "quick": return [f"shred -v -n 1 -z {shlex.quote(device_path)}"]
            if mode == "paranoid": return [f"shred -v -n 3 -z {shlex.quote(device_path)}"]
            if mode == "crypto":
                if devtype == "nvme": return [f"nvme format {shlex.quote(device_path)} --ses=1"]
                return [
                    f"hdparm --user-master u --security-set-pass p {shlex.quote(device_path)}",
                    f"hdparm --user-master u --security-erase p {shlex.quote(device_path)}"
                ]
            if mode == "forensic":
                if devtype == "nvme": return [f"nvme format {shlex.quote(device_path)} --ses=2"]
                return [
                    f"hdparm --dco-restore {shlex.quote(device_path)}",
                    f"hdparm -N p`hdparm -N {shlex.quote(device_path)} | grep 'max' | cut -d/ -f2` {shlex.quote(device_path)}",
                    f"hdparm --user-master u --security-set-pass p {shlex.quote(device_path)}",
                    f"hdparm --user-master u --security-erase-enhanced p {shlex.quote(device_path)}"
                ]
        else:
            # On Windows, we use the built-in 'format' command with the '/p' flag for overwriting.
            drive_letter = device_path.strip()[:2]
            if mode == "quick": return [f'format {drive_letter} /fs:NTFS /y /p:0']
            if mode == "paranoid": return [f'format {drive_letter} /fs:NTFS /y /p:2']
            if mode in ["crypto", "forensic"]:
                logger.warning("Crypto/Forensic on Windows defaults to the most secure software wipe (3-pass).")
                return [f'format {drive_letter} /fs:NTFS /y /p:2']

        raise RunnerError(f"Unknown mode '{mode}' or unsupported OS.")

    def _run_command_with_progress(self, cmd: str):
        """
        Executes a command and captures its live output to report progress.
        This is the new core of the runner, enabling the real-time UI.
        """
        logger.info(f"Running: {cmd}")
        # Use Popen for non-blocking, real-time stream reading.
        # On Windows, shell=True is often required for system commands like 'format'.
        use_shell = not self.is_linux
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=use_shell,
            bufsize=1 # Line-buffered
        )
        
        stdout_full, stderr_full = "", ""
        
        # Determine which stream to read for progress based on the command.
        stream = process.stderr if 'shred' in cmd else process.stdout

        for line in iter(stream.readline, ''):
            if self.is_linux and 'shred' in cmd:
                # Shred prints progress to stderr, e.g., "shred: /dev/sdb: pass 1/4 (random)...25%"
                match = re.search(r'(\d+)%', line)
                if match:
                    progress = int(match.group(1))
                    self._update_status("wiping", progress, f"Executing: {cmd.split(' ')[0]}")
            elif not self.is_linux and 'format' in cmd:
                # Windows format command prints "XX.XX percent completed." to stdout.
                match = re.search(r'(\d+\.\d+)\spercent', line)
                if match:
                    progress = int(float(match.group(1)))
                    self._update_status("wiping", progress, f"Executing: {cmd.split(' ')[0]}")
            
            # Store the full output for logging purposes.
            if stream is process.stdout: stdout_full += line
            else: stderr_full += line

        # Wait for the process to finish and get the return code.
        process.wait()
        returncode = process.returncode
        
        # After the loop, read any remaining output.
        stdout_rem, stderr_rem = process.communicate()
        stdout_full += stdout_rem
        stderr_full += stderr_rem

        return {"cmd": cmd, "returncode": returncode, "stdout": stdout_full, "stderr": stderr_full}

    def _simulate_command_with_progress(self, cmd: str):
        """Simulates running a command with fake progress for dry-run mode."""
        logger.info(f"[SIMULATE] {cmd}")
        for p in range(0, 101, 10):
            self._update_status("wiping", p, f"Simulating: {cmd.split(' ')[0]}")
            time.sleep(0.2)
        return {"cmd": cmd, "returncode": 0, "stdout": f"[SIMULATED] {cmd}", "stderr": ""}

    def run_wipe(self, device_info: dict, mode: str):
        """
        Main method to execute a full wipe operation on a device.
        This function orchestrates the entire process from command preparation
        to execution and final logging.
        """
        device_path = self._get_device_path(device_info)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = re.sub(r'[^\w\-_.]', '_', device_path)
        log_file = os.path.join(self.log_dir, f"wipe_{safe_name}_{timestamp}.log")

        try:
            self._update_status("wiping", 0, f"Preparing to wipe {device_path} with mode '{mode}'.")
            commands = self._prepare_commands(device_path, mode)
            
            # For commands without granular progress (like hdparm), we'll show progress
            # based on the number of commands completed.
            total_commands = len(commands)
            overall_progress_step = 100 / total_commands if total_commands > 0 else 0

        except RunnerError as e:
            self._update_status("failed", 0, str(e))
            return {"success": False, "error": str(e), "device_details": device_info, "wipe_mode": mode}

        results, overall_success = [], True
        for i, cmd in enumerate(commands):
            # Update progress based on the step we are on.
            current_base_progress = i * overall_progress_step
            self._update_status("wiping", int(current_base_progress), f"Starting step {i+1}/{total_commands}: {cmd.split(' ')[0]}")
            
            # Decide whether to run the real or simulated command.
            if self.dry_run:
                res = self._simulate_command_with_progress(cmd)
            else:
                # For commands that don't give percentage output, we just run them and
                # show a static progress for that step.
                if 'shred' in cmd or 'format' in cmd:
                    res = self._run_command_with_progress(cmd)
                else:
                    # For hdparm/nvme, we simulate the progress for that step as they are quick.
                    self._update_status("wiping", int(current_base_progress + (overall_progress_step / 2)), "Executing hardware command...")
                    res = subprocess.run(cmd, capture_output=True, text=True, shell=self.is_linux)
                    res = {"cmd": cmd, "returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
                    time.sleep(1) # Give a feeling of execution time.
            
            results.append(res)
            if res["returncode"] != 0:
                overall_success = False
                error_message = f"Command failed with code {res['returncode']}. Stderr: {res.get('stderr', 'N/A')}"
                self._update_status("failed", int(current_base_progress), error_message)
                break
        
        if overall_success:
            self._update_status("success", 100, "Wipe completed successfully.")

        # --- Final Logging and Result Generation ---
        system_info = {"hostname": socket.gethostname(), "os": platform.platform()}
        log_data = {
            "device_details": device_info, "wipe_mode": mode, "timestamp_utc": timestamp,
            "success": overall_success, "system_info": system_info, "tool_version": TOOL_VERSION,
            "results": results, "log_file": log_file,
            "is_simulation": self.dry_run
        }

        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=4, default=str)

        log_hash = "N/A"
        if overall_success:
            hasher = hashlib.sha256()
            with open(log_file, 'rb') as f:
                hasher.update(f.read())
            log_hash = hasher.hexdigest()
        
        final_result = {**log_data, "verification": {"log_hash_sha256": log_hash}}
        return final_result
