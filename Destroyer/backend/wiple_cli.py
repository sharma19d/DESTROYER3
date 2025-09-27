# backend/wiple_cli.py
"""
backend/wiple_cli.py

Interactive CLI for Destroyer.
--- NEW: Main menu to select between Local, Remote, or Demo mode ---
"""

import sys
import os
import requests # <-- NEW: For making API calls
import json
import getpass # <-- NEW: For securely entering API key

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import WipeRunner
from device_detect import list_devices
from certificate import generate_certificate
from verifier import verify_certificate, verify_qr


def print_result(result):
    """Helper function to print wipe results consistently."""
    print("\n=== Wipe Result ===")
    success_key = "success"
    # In demo mode, we use a different key
    if result.get("is_simulation"):
        success_key = "status"
        print(f"Status: {result.get(success_key, 'N/A')}")
    else:
        print(f"Success: {result.get(success_key)}")

    print(f"Log file: {result.get('log_file', 'N/A')}")

    if "results" in result and result["results"]:
        for r in result["results"]:
            print(f"- {r['cmd']} -> return {r['returncode']}")
    elif "error" in result:
        print(f"❌ Error: {result['error']}")

    # Stop if the wipe failed before trying to generate certs
    if not result.get('success'):
        print("\nWipe failed. Certificate generation skipped.")
        return

    # In remote mode, certificates are on the remote machine
    if result.get('certificates'):
        print("\n✅ Certificates generated on remote machine:")
        for k, v in result["certificates"].items():
            print(f"- {k.upper()}: {v}")
    # In local/demo mode, we generate and verify them
    else:
        # Generate certificate
        cert_files = generate_certificate(result, output_dir="samples")
        print("\n✅ Certificates generated:")
        for k, v in cert_files.items():
            print(f"- {k.upper()}: {v}")

        print("\n🔍 Verifying JSON Certificate...")
        verification = verify_certificate(cert_files["json"])
        if verification["valid"]:
            print("✅ JSON Certificate is valid.")
        else:
            print(f"❌ JSON Certificate invalid: {verification['error']}")

        print("\n🔍 Verifying QR Certificate...")
        qr_verification = verify_qr(cert_files["qr"])
        if qr_verification["valid"]:
            print("✅ QR Certificate is valid (scanable).")
        else:
            print(f"❌ QR Certificate invalid: {qr_verification['error']}")


def run_local_wipe():
    """Contains the original logic for wiping the local machine."""
    print("\n--- Mode: Wipe Current System ---")
    
    # This section is the original code from your wiple_cli.py
    devices = list_devices()
    if not devices:
        print("No drives detected.")
        return

    print("\nAvailable Drives:")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['path']} - {d['size']} mounted: {d['mountpoint']}")

    try:
        choice = int(input("\nSelect device number: ")) - 1
        device_info = devices[choice]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return

    print("\nSelect Wipe Mode:")
    print("1. Quick (1-pass software wipe)")
    print("2. Paranoid (3-pass software wipe, DoD standard)")
    print("3. Crypto (Hardware secure erase)")
    print("4. Forensic (Hardware erase with HPA/DCO removal - MOST SECURE)")

    mode_choice = input("Enter choice [1/2/3/4]: ").strip()
    mode_map = {"1": "quick", "2": "paranoid", "3": "crypto", "4": "forensic"}
    if mode_choice not in mode_map:
        print("Invalid mode choice.")
        return
    mode = mode_map[mode_choice]

    execute_choice = input("\nExecute for real? This will permanently destroy data. (y/N): ").strip().lower()
    execute = execute_choice == "y"

    runner = WipeRunner(dry_run=not execute)
    result = runner.run_wipe(device_info, mode=mode, execute=execute)
    
    print_result(result)


def run_remote_wipe():
    """NEW: Handles the logic for wiping a remote system via the API."""
    print("\n--- Mode: Wipe Remote System ---")
    
    # 1. Get connection details
    target_ip = input("Enter the target machine IP address: ").strip()
    api_key = getpass.getpass("Enter the API Key: ").strip()
    
    base_url = f"http://{target_ip}:5000"
    headers = {"X-API-Key": api_key}

    # 2. Fetch remote devices
    try:
        print(f"\nConnecting to {target_ip} to get device list...")
        response = requests.get(f"{base_url}/devices", headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Error: Failed to connect or authenticate. Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return
            
        devices = response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: Could not connect to the target machine. {e}")
        return

    if not devices:
        print("No drives detected on the remote machine.")
        return

    print("\nAvailable Remote Drives:")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['path']} - {d['size']} (Model: {d.get('model', 'N/A')})")

    try:
        choice = int(input("\nSelect remote device number to WIPE: ")) - 1
        device_info = devices[choice]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return

    # 3. Select wipe mode
    print("\nSelect Wipe Mode:")
    print("1. Quick\n2. Paranoid\n3. Crypto\n4. Forensic")
    mode_choice = input("Enter choice [1/2/3/4]: ").strip()
    mode_map = {"1": "quick", "2": "paranoid", "3": "crypto", "4": "forensic"}
    if mode_choice not in mode_map:
        print("Invalid mode choice.")
        return
    mode = mode_map[mode_choice]

    # 4. Final confirmation and execution
    print("\n" + "="*50)
    print("⚠️  CRITICAL WARNING ⚠️")
    print(f"You are about to remotely and PERMANENTLY WIPE the following drive:")
    print(f"  TARGET IP: {target_ip}")
    print(f"  DEVICE:    {device_info['path']}")
    print(f"  MODE:      {mode.upper()}")
    print("This action cannot be undone.")
    print("="*50)
    
    confirm = input('Type "yes" to proceed: ').strip().lower()
    if confirm != "yes":
        print("Remote wipe cancelled.")
        return
        
    # 5. Send wipe command
    payload = {
        "device": device_info['path'],
        "mode": mode,
        "execute": True
    }
    
    print("\nSending remote wipe command...")
    try:
        response = requests.post(f"{base_url}/wipe", headers=headers, json=payload, timeout=7200) # Long timeout for wipe
        result = response.json()
        print_result(result)
    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error during wipe command. {e}")


def run_demo_mode():
    """NEW: Runs a safe, local simulation and generates a demo certificate."""
    print("\n--- Mode: Demo / Simulation ---")
    print("This mode will simulate a wipe and generate a sample certificate without destroying any data.")

    devices = list_devices()
    if not devices:
        print("No drives detected to simulate on.")
        return

    print("\nAvailable Drives for Simulation:")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['path']} - {d['size']} mounted: {d['mountpoint']}")

    try:
        choice = int(input("\nSelect device number to simulate on: ")) - 1
        device_info = devices[choice]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return

    # Mode selection is the same as local
    print("\nSelect Wipe Mode to Simulate:")
    print("1. Quick\n2. Paranoid\n3. Crypto\n4. Forensic")
    mode_choice = input("Enter choice [1/2/3/4]: ").strip()
    mode_map = {"1": "quick", "2": "paranoid", "3": "crypto", "4": "forensic"}
    if mode_choice not in mode_map:
        print("Invalid mode choice.")
        return
    mode = mode_map[mode_choice]
    
    # Run the wipe in dry_run mode (execute=False)
    runner = WipeRunner(dry_run=True)
    result = runner.run_wipe(device_info, mode=mode, execute=False)
    
    # CRITICAL: Add the flag for certificate.py to know this is a simulation
    result["is_simulation"] = True
    
    print_result(result)


def main():
    """Main function to display the menu and route to the correct mode."""
    print("=== Destroyer CLI v2.0 ===")
    
    while True:
        print("\nPlease select an operation mode:")
        print("  1. Wipe Current System")
        print("  2. Wipe Remote System")
        print("  3. Run Demo / Simulation")
        print("  4. Exit")
        
        choice = input("\nEnter your choice [1/2/3/4]: ").strip()
        
        if choice == '1':
            run_local_wipe()
        elif choice == '2':
            run_remote_wipe()
        elif choice == '3':
            run_demo_mode()
        elif choice == '4':
            print("Exiting Destroyer.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()