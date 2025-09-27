# backend/api.py
"""
backend/api.py

Flask API for Destroyer.
Features:
- List remote devices
- Run wipe (safe dry-run by default)
- Verify wipe certificates (JSON/QR)
- SECURED WITH API KEY
"""

import os
import json
from functools import wraps
from flask import Flask, request, jsonify
from utils.logger import logger
from runner import WipeRunner
from certificate import generate_certificate
from verifier import verify_certificate, verify_qr
# --- NEW: Import list_devices ---
from device_detect import list_devices

app = Flask(__name__)

# --- NEW: Simple API Key for security ---
# In a real application, this should come from an environment variable or a secure config file.
API_KEY = "destroyer-secret-key-12345"

# --- NEW: Decorator to protect endpoints ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'X-API-Key' not in request.headers or request.headers['X-API-Key'] != API_KEY:
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():
    return jsonify({"message": "Destroyer API running"})


# --- NEW: Endpoint to list devices on the remote machine ---
@app.route("/devices", methods=["GET"])
@require_api_key
def get_devices():
    """
    Lists all detected storage devices.
    """
    try:
        devices = list_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/wipe", methods=["POST"])
@require_api_key # --- MODIFIED: Added security
def wipe():
    logger.info("Received /wipe request")
    """
    Run a wipe.
    JSON body:
    {
        "device": "/dev/sdb" or "C:\\\\",
        "mode": "quick|paranoid|crypto|forensic",
        "execute": false
    }
    Header:
    {
        "X-API-Key": "your-secret-key"
    }
    """
    try:
        data = request.json
        device = data.get("device")
        mode = data.get("mode", "quick")
        execute = bool(data.get("execute", False))

        if not device:
            return jsonify({"success": False, "error": "Device path is required."}), 400

        runner = WipeRunner(dry_run=not execute)
        result = runner.run_wipe(device, mode=mode, execute=execute)

        # Generate cert only on successful, executed wipe
        if result.get("success") and execute:
            cert_files = generate_certificate(result, output_dir="samples")
            result["certificates"] = cert_files

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/verify/json", methods=["POST"])
@require_api_key # --- MODIFIED: Added security
def verify_json():
    """
    Verify JSON certificate.
    Request:
        multipart/form-data with "file"
    """
    try:
        if "file" not in request.files:
            return jsonify({"valid": False, "error": "No file uploaded"}), 400

        f = request.files["file"]
        # Ensure the samples directory exists for saving the uploaded file
        os.makedirs("samples", exist_ok=True)
        path = os.path.join("samples", f.filename)
        f.save(path)

        result = verify_certificate(path)
        return jsonify(result)

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 400


@app.route("/verify/qr", methods=["POST"])
@require_api_key # --- MODIFIED: Added security
def verify_qr_api():
    """
    Verify QR certificate (PNG).
    Request:
        multipart/form-data with "file"
    """
    try:
        if "file" not in request.files:
            return jsonify({"valid": False, "error": "No file uploaded"}), 400

        f = request.files["file"]
        # Ensure the samples directory exists for saving the uploaded file
        os.makedirs("samples", exist_ok=True)
        path = os.path.join("samples", f.filename)
        f.save(path)

        result = verify_qr(path)
        return jsonify(result)

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 400


if __name__ == "__main__":
    # For production, consider using a proper WSGI server like Gunicorn or Waitress.
    # To enable HTTPS, you would use: app.run(ssl_context=('cert.pem', 'key.pem'))
    app.run(host="0.0.0.0", port=5000, debug=True)