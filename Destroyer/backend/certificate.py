# backend/certificate.py
"""
backend/certificate.py

Generates professional certificates using OS-agnostic relative paths to ensure
it works perfectly on both Windows and Linux.
--- MODIFIED: Now supports generating 'Simulation' certificates for demo mode. ---
"""
import json
import qrcode
import io
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- Use paths relative to this file for 100% portability ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

def generate_certificate(result: dict, output_dir=None): # The output_dir is accepted but ignored
    """
    Generate a professional wipe certificate (PDF, JSON, QR) from a result dict.
    """
    # This function now manages its own output directory for consistency.
    output_dir = SAMPLES_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # --- NEW: Check if this is a simulation run ---
    is_simulation = result.get("is_simulation", False)

    # Use the result from the runner as the single source of truth
    cert_data = result
    timestamp = cert_data.get("timestamp_utc", datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"))
    device_path = cert_data.get("device_details", {}).get("path", "unknown_device")
    
    # Sanitize filename for all operating systems
    safe_name = device_path.replace("/", "_").replace("\\", "_").replace(":", "")
    base_filename = f"certificate_{safe_name}_{timestamp}"
    cert_data["certificate_id"] = base_filename

    # --- MODIFIED: Adjust status based on simulation mode ---
    if is_simulation:
        cert_data["status"] = "Simulation Success"
        cert_data["is_simulation"] = True
    else:
        cert_data["status"] = "Success" if cert_data.get("success") else "Failed"

    # 1. Save JSON Certificate
    json_path = os.path.join(output_dir, f"{base_filename}.json")
    with open(json_path, "w") as f:
        json.dump(cert_data, f, indent=4, default=str)

    # 2. Generate QR Code (no changes needed for QR)
    qr_payload = {
        "certificate_id": cert_data["certificate_id"],
        "log_hash": cert_data.get("verification", {}).get("log_hash_sha256", "N/A")
    }
    qr_img = qrcode.make(json.dumps(qr_payload))
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_path = os.path.join(output_dir, f"{base_filename}.png")
    with open(qr_path, "wb") as f:
        f.write(qr_buf.getvalue())

    # 3. Generate PDF Certificate
    pdf_path = os.path.join(output_dir, f"{base_filename}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()
    
    # --- PDF Design ---
    c.setStrokeColorRGB(0.1, 0.2, 0.5)
    c.setLineWidth(5)
    c.rect(20, 20, width - 40, height - 40)
    
    # --- MODIFIED: Main title changes for simulation ---
    title = "Certificate of Data Destruction"
    if is_simulation:
        title += " (SIMULATION)"
    
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(0.1, 0.2, 0.5)
    c.drawCentredString(width / 2.0, height - 70, title)
    
    # --- NEW: Add a prominent warning for simulation certificates ---
    if is_simulation:
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.red)
        c.drawCentredString(width / 2.0, height - 100, "--- DEMO MODE: NO DATA WAS DESTROYED ---")

    logo_path = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_path):
        c.drawImage(logo_path, (width / 2.0) - 40, height - 170, width=80, height=80, mask='auto')

    c.setFillColor(colors.black)
    y_position = height - 220
    
    # Table 1: Device Details
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_position, "Target Medium Details")
    device_details = cert_data.get("device_details", {})
    
    # --- MODIFIED: Status text changes for simulation ---
    status_text = "✅ SUCCESS" if cert_data.get("success") else "❌ FAILED"
    if is_simulation:
        status_text = "🔵 SIMULATION SUCCESS"
        
    device_data = [
        ["Device Path:", Paragraph(device_details.get("path", "N/A"), styles['Normal'])],
        ["Device Model:", device_details.get("model", "N/A")],
        ["Serial Number:", device_details.get("serial", "N/A")],
        ["Wipe Method:", cert_data.get("wipe_mode", "N/A").title()],
        ["Status:", status_text],
    ]
    device_table = Table(device_data, colWidths=[120, 380])
    device_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    w, h = device_table.wrap(0, 0)
    device_table.drawOn(c, 50, y_position - h - 10)
    y_position -= h + 50

    # Table 2: System Info (No changes needed)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_position, "System & Tool Information")
    system_info = cert_data.get("system_info", {})
    system_data = [
        ["Hostname:", system_info.get("hostname", "N/A")],
        ["Operating System:", Paragraph(system_info.get("os", "N/A"), styles['Normal'])],
        ["Tool Version:", cert_data.get("tool_version", "N/A")],
        ["Timestamp (UTC):", timestamp],
    ]
    system_table = Table(system_data, colWidths=[120, 380])
    system_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    w, h = system_table.wrap(0, 0)
    system_table.drawOn(c, 50, y_position - h - 10)
    y_position -= h + 50

    # Table 3: Verification (No changes needed)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_position, "Verification & Integrity")
    verification_info = cert_data.get("verification", {})
    verification_data = [["Log File Hash (SHA-256):", Paragraph(verification_info.get("log_hash_sha256", "N/A"), styles['Normal'])]]
    verification_table = Table(verification_data, colWidths=[150, 350])
    verification_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    w, h = verification_table.wrap(0, 0)
    verification_table.drawOn(c, 50, y_position - h - 10)

    # QR Code on PDF
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), 50, 50, width=100, height=100, mask='auto')
    c.save()

    return {"json": json_path, "pdf": pdf_path, "qr": qr_path}