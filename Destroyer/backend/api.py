# backend/api.py
"""
backend/api.py

Flask API for Destroyer, rewritten for a real-time UI.
Features:
- Asynchronous wipe endpoint that starts jobs in the background.
- Status endpoint for the UI to poll for live progress updates.
- Secured with API Key and now includes CORS for web-based frontends.
"""

import os
import json
import threading
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS # NEW: Import CORS

from utils.logger import logger
from runner import WipeRunner
from certificate import generate_certificate
from verifier import verify_certificate, verify_qr
from device_detect import list_devices

app = Flask(__name__)

# --- NEW: Enable Cross-Origin Resource Sharing ---
# This is CRITICAL for your Electron/React UI to communicate with this server.
CORS(app) 

# In a real app, get this from an environment variable.
API_KEY = "destroyer-secret-key-12345"

# --- NEW: Global State Management for Wipe Progress ---
# This dictionary will hold the live status of any wipe operation.
# It's accessible by all API threads. We use a lock to prevent race conditions
# when multiple requests try to access it at the same time.
WIPE_STATUS = {
    "status": "idle", # idle, wiping, success, failed
    "progress": 0,
    "message": "Awaiting commands.",
    "device_details": None,
    "final_result": None
}
status_lock = threading.Lock()

def require_api_key(f):
    """Decorator to protect endpoints with an API key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'X-API-Key' not in request.headers or request.headers['X-API-Key'] != API_KEY:
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 401
        return f(*args, **kwargs)
    return decorated_function

def api_status_callback(update):
    """
    NEW: This function is the bridge between the WipeRunner and the API.
    The runner will call this function with progress updates, and this function
    will safely update the global WIPE_STATUS dictionary.
    """
    with status_lock:
        WIPE_STATUS["status"] = update.get("status", WIPE_STATUS["status"])
        WIPE_STATUS["progress"] = update.get("progress", WIPE_STATUS["progress"])
        WIPE_STATUS["message"] = update.get("message", WIPE_STATUS["message"])

def wipe_thread_target(device_info, mode, dry_run):
    """
    NEW: This function is the target for our background thread. It runs the
    actual wipe and updates the final result when it's done.
    """
    try:
        runner = WipeRunner(dry_run=dry_run, status_callback=api_status_callback)
        final_result = runner.run_wipe(device_info, mode=mode)
        
        # Once finished, store the full result.
        with status_lock:
            WIPE_STATUS["final_result"] = final_result
            # The runner's final status is the source of truth.
            if final_result.get("success"):
                WIPE_STATUS["status"] = "success"
            else:
                WIPE_STATUS["status"] = "failed"
                WIPE_STATUS["message"] = final_result.get("error", "An unknown error occurred.")

    except Exception as e:
        logger.error(f"Exception in wipe thread: {e}")
        with status_lock:
            WIPE_STATUS["status"] = "failed"
            WIPE_STATUS["message"] = str(e)


@app.route("/")
def index():
    return jsonify({"message": "Destroyer API v2.0 running"})

@app.route("/devices", methods=["GET"])
@require_api_key
def get_devices():
    """Lists all detected storage devices."""
    try:
        devices = list_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/wipe", methods=["POST"])
@require_api_key
def wipe():
    """
    --- REWRITTEN: Now starts the wipe in a background thread ---
    """
    with status_lock:
        if WIPE_STATUS["status"] == "wiping":
            return jsonify({"error": "A wipe is already in progress."}), 409 # 409 Conflict

        # Reset status for the new job
        WIPE_STATUS["status"] = "wiping"
        WIPE_STATUS["progress"] = 0
        WIPE_STATUS["message"] = "Initializing wipe..."
        WIPE_STATUS["final_result"] = None
        
        data = request.json
        device_info = data.get("device")
        mode = data.get("mode", "quick")
        execute = bool(data.get("execute", False))
        
        if not device_info:
            return jsonify({"error": "Device info is required."}), 400

        WIPE_STATUS["device_details"] = device_info

        # Start the wipe in a new thread so we can return immediately
        thread = threading.Thread(target=wipe_thread_target, args=(device_info, mode, not execute))
        thread.start()

        return jsonify({"message": "Wipe process started successfully."}), 202 # 202 Accepted

@app.route("/wipe-status", methods=["GET"])
@require_api_key
def get_wipe_status():
    """
    NEW: The UI will call this endpoint repeatedly to get live updates.
    """
    with status_lock:
        # If the wipe is done, we might want to generate certificates
        if WIPE_STATUS["status"] in ["success", "failed"] and WIPE_STATUS["final_result"] and "certificates" not in WIPE_STATUS["final_result"]:
            result = WIPE_STATUS["final_result"]
            # Generate certs only on successful, executed wipe
            if result.get("success") and not result.get("is_simulation"):
                cert_files = generate_certificate(result, output_dir="samples")
                WIPE_STATUS["final_result"]["certificates"] = cert_files

        return jsonify(WIPE_STATUS)

# --- Verification endpoints remain unchanged for now ---
@app.route("/verify/json", methods=["POST"])
@require_api_key
def verify_json():
    # ... (code is the same as before)
    pass 

@app.route("/verify/qr", methods=["POST"])
@require_api_key
def verify_qr_api():
    # ... (code is the same as before)
    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
