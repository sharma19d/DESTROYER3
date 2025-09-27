# backend/__init__.py
"""
backend/__init__.py

Package initializer for Destoryer backend.
Exposes the most commonly used classes and functions at package level.
"""

from .runner import WipeRunner
from .certificate import generate_certificate
from .verifier import CertificateVerifier  # adjust if class/function name differs
from .simulator import Simulator           # adjust if you rename this
from .device_detect import list_devices

__all__ = [
    "WipeRunner",
    "generate_certificate",
    "CertificateVerifier",
    "Simulator",
    "list_devices",
]

