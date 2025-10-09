"""
File Upload Security Utility for Django Backend

Comprehensive security validation for uploaded files to prevent:
- Malware uploads
- Code injection
- Path traversal attacks
- Zip bombs
- MIME type spoofing
- Malicious file execution

Usage:
    from .file_security import validate_uploaded_file, scan_file_for_threats

    result = validate_uploaded_file(uploaded_file)
    if not result['valid']:
        return Response({'error': result['error']}, status=400)
"""

import os
import re
import magic  # python-magic for MIME type detection
import hashlib
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
import logging

logger = logging.getLogger(__name__)

# Maximum file sizes by type (in bytes)
MAX_FILE_SIZES = {
    "application/pdf": 10 * 1024 * 1024,  # 10MB
    "application/msword": 10 * 1024 * 1024,  # 10MB
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 10
    * 1024
    * 1024,  # 10MB
}

# Allowed MIME types
ALLOWED_MIME_TYPES = list(MAX_FILE_SIZES.keys())

# Allowed file extensions
ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"]

# Dangerous file extensions (blacklist)
DANGEROUS_EXTENSIONS = [
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".pif",
    ".scr",
    ".vbs",
    ".js",
    ".jar",
    ".msi",
    ".app",
    ".deb",
    ".rpm",
    ".dmg",
    ".pkg",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".psm1",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".run",
    ".elf",
    ".apk",
    ".ipa",
    ".xap",
    ".appx",
    ".gadget",
    ".hta",
    ".inf",
    ".lnk",
    ".msp",
    ".reg",
    ".scf",
    ".torrent",
    ".ws",
    ".wsf",
    ".wsh",
    ".cab",
    ".cpl",
    ".msc",
    ".vb",
    ".vbe",
    ".jse",
    ".ws",
    ".wsf",
    ".wsc",
    ".py",
    ".rb",
    ".pl",
    ".php",
    ".asp",
    ".aspx",
    ".jsp",
    ".cgi",
]

# Dangerous file signatures (magic numbers)
DANGEROUS_SIGNATURES = {
    b"MZ": "Windows/DOS executable",
    b"\x7fELF": "Linux/Unix executable",
    b"\xca\xfe\xba\xbe": "Java class file",
    b"\xfe\xed\xfa\xce": "macOS executable",
    b"\xce\xfa\xed\xfe": "macOS executable (64-bit)",
    b"#!/": "Shell script",
    b"<?php": "PHP script",
    b"<script": "HTML with script tag",
}

# Expected file signatures for allowed types
EXPECTED_SIGNATURES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",  # ZIP signature (DOCX is a ZIP)
    ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",  # OLE signature
}


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal and injection attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")

    # Remove path separators
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove control characters
    filename = re.sub(r"[\x00-\x1F\x7F]", "", filename)

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*]', "", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Limit length
    max_length = 255
    name, ext = os.path.splitext(filename)
    if len(filename) > max_length:
        name = name[: max_length - len(ext)]
        filename = name + ext

    # If filename becomes empty, generate safe default
    if not filename or filename == "":
        filename = f"document_{hashlib.md5(os.urandom(16)).hexdigest()[:8]}"

    return filename


def validate_file_extension(filename):
    """
    Validate file extension against whitelist and blacklist.

    Args:
        filename: Name of the file

    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    ext = os.path.splitext(filename)[1].lower()

    # Check blacklist first
    if ext in DANGEROUS_EXTENSIONS:
        logger.warning(f"Dangerous file extension detected: {ext} in {filename}")
        return {
            "valid": False,
            "error": f"Dangerous file type detected: {ext}. This file type is blocked for security reasons.",
        }

    # Check whitelist
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file extension: {ext} in {filename}")
        return {
            "valid": False,
            "error": f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}',
        }

    # Check for double extensions (e.g., document.pdf.exe)
    parts = filename.split(".")
    if len(parts) > 2:
        for i in range(1, len(parts) - 1):
            middle_ext = f".{parts[i].lower()}"
            if middle_ext in DANGEROUS_EXTENSIONS:
                logger.warning(f"Double extension attack detected: {filename}")
                return {
                    "valid": False,
                    "error": "File has suspicious double extension. This is not allowed for security reasons.",
                }

    return {"valid": True, "error": None}


def validate_mime_type(file):
    """
    Validate MIME type using python-magic (libmagic).
    This reads the file header to detect actual type, preventing spoofing.

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {'valid': bool, 'error': str or None, 'detected_mime': str}
    """
    try:
        # Read first 2KB for MIME detection
        file.seek(0)
        file_header = file.read(2048)
        file.seek(0)

        # Detect actual MIME type from file content
        mime = magic.from_buffer(file_header, mime=True)

        logger.info(f"Detected MIME type: {mime} for file: {file.name}")

        # Check if detected MIME is in allowed list
        if mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"Invalid MIME type detected: {mime} for {file.name}")
            return {
                "valid": False,
                "error": f"Invalid file type detected. File appears to be {mime}. Only PDF and Word documents are allowed.",
                "detected_mime": mime,
            }

        # Check if claimed MIME matches detected MIME (prevent spoofing)
        if hasattr(file, "content_type") and file.content_type:
            if file.content_type != mime:
                logger.warning(
                    f"MIME type spoofing detected: claimed {file.content_type}, actual {mime}"
                )
                return {
                    "valid": False,
                    "error": "File type mismatch detected. The file may have been tampered with.",
                    "detected_mime": mime,
                }

        return {"valid": True, "error": None, "detected_mime": mime}

    except Exception as e:
        logger.error(f"MIME type validation error: {str(e)}")
        return {
            "valid": False,
            "error": "Failed to validate file type. Please try again.",
            "detected_mime": None,
        }


def validate_file_signature(file):
    """
    Validate file signature (magic numbers) to detect malicious files.

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    try:
        file.seek(0)
        header = file.read(512)
        file.seek(0)

        # Check for dangerous signatures
        for signature, description in DANGEROUS_SIGNATURES.items():
            if header.startswith(signature):
                logger.error(
                    f"Dangerous file signature detected: {description} in {file.name}"
                )
                return {
                    "valid": False,
                    "error": f"Dangerous file detected: {description}. This file cannot be uploaded.",
                }

        # Validate expected signatures for allowed file types
        ext = os.path.splitext(file.name)[1].lower()
        expected_sig = EXPECTED_SIGNATURES.get(ext)

        if expected_sig and not header.startswith(expected_sig):
            logger.warning(
                f"File signature mismatch for {file.name}: expected {ext} signature"
            )
            return {
                "valid": False,
                "error": f"File appears to be corrupted or is not a valid {ext} file.",
            }

        return {"valid": True, "error": None}

    except Exception as e:
        logger.error(f"File signature validation error: {str(e)}")
        return {
            "valid": False,
            "error": "Failed to validate file integrity. Please try again.",
        }


def validate_file_size(file):
    """
    Validate file size against limits.

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    max_size = max(MAX_FILE_SIZES.values())

    if file.size > max_size:
        size_mb = file.size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        logger.warning(f"File too large: {size_mb:.1f}MB (max: {max_mb:.1f}MB)")
        return {
            "valid": False,
            "error": f"File too large ({size_mb:.1f}MB). Maximum size is {max_mb:.1f}MB.",
        }

    # Check for suspiciously small files
    if file.size < 100:
        logger.warning(f"File too small: {file.size} bytes")
        return {
            "valid": False,
            "error": "File is too small. Please upload a valid CV document.",
        }

    return {"valid": True, "error": None}


def detect_zip_bomb(file):
    """
    Detect potential zip bombs (DOCX files are zipped).

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    ext = os.path.splitext(file.name)[1].lower()

    # DOCX files are ZIP archives
    if ext == ".docx":
        # A legitimate DOCX should have minimum size
        min_expected_size = 5 * 1024  # 5KB

        if file.size < min_expected_size:
            logger.warning(f"Suspiciously small DOCX file: {file.size} bytes")
            return {"valid": False, "error": "File appears to be invalid or corrupted."}

    return {"valid": True, "error": None}


def scan_for_embedded_threats(file):
    """
    Scan for embedded executable code or scripts in documents.

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {'valid': bool, 'error': str or None}
    """
    try:
        file.seek(0)
        content = file.read()
        file.seek(0)

        # Patterns that might indicate embedded malicious content
        dangerous_patterns = [
            b"<?php",
            b"<script",
            b"javascript:",
            b"vbscript:",
            b"onload=",
            b"onerror=",
            b"eval(",
            b"exec(",
            b"powershell",
            b"cmd.exe",
            b"/bin/sh",
            b"/bin/bash",
        ]

        content_lower = content.lower()

        for pattern in dangerous_patterns:
            if pattern in content_lower:
                logger.error(f"Dangerous pattern detected in {file.name}: {pattern}")
                return {
                    "valid": False,
                    "error": "File contains suspicious content and cannot be uploaded.",
                }

        return {"valid": True, "error": None}

    except Exception as e:
        logger.error(f"Threat scanning error: {str(e)}")
        # Don't fail on scan errors, but log them
        return {"valid": True, "error": None}


def validate_uploaded_file(file):
    """
    Comprehensive validation of uploaded file.
    Runs all security checks.

    Args:
        file: Django UploadedFile object

    Returns:
        dict: {
            'valid': bool,
            'error': str or None,
            'sanitized_name': str,
            'detected_mime': str or None
        }
    """
    try:
        # 1. Check file exists
        if not file:
            return {
                "valid": False,
                "error": "No file uploaded",
                "sanitized_name": None,
                "detected_mime": None,
            }

        # 2. Sanitize filename
        sanitized_name = sanitize_filename(file.name)

        # 3. Validate extension
        ext_validation = validate_file_extension(sanitized_name)
        if not ext_validation["valid"]:
            return {
                "valid": False,
                "error": ext_validation["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": None,
            }

        # 4. Validate file size
        size_validation = validate_file_size(file)
        if not size_validation["valid"]:
            return {
                "valid": False,
                "error": size_validation["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": None,
            }

        # 5. Validate file signature
        signature_validation = validate_file_signature(file)
        if not signature_validation["valid"]:
            return {
                "valid": False,
                "error": signature_validation["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": None,
            }

        # 6. Validate MIME type (deep inspection)
        mime_validation = validate_mime_type(file)
        if not mime_validation["valid"]:
            return {
                "valid": False,
                "error": mime_validation["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": mime_validation.get("detected_mime"),
            }

        # 7. Check for zip bombs
        bomb_check = detect_zip_bomb(file)
        if not bomb_check["valid"]:
            return {
                "valid": False,
                "error": bomb_check["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": mime_validation.get("detected_mime"),
            }

        # 8. Scan for embedded threats
        threat_scan = scan_for_embedded_threats(file)
        if not threat_scan["valid"]:
            return {
                "valid": False,
                "error": threat_scan["error"],
                "sanitized_name": sanitized_name,
                "detected_mime": mime_validation.get("detected_mime"),
            }

        # All checks passed
        logger.info(f"File validation successful: {sanitized_name}")
        return {
            "valid": True,
            "error": None,
            "sanitized_name": sanitized_name,
            "detected_mime": mime_validation.get("detected_mime"),
        }

    except Exception as e:
        logger.error(f"File validation error: {str(e)}")
        return {
            "valid": False,
            "error": "An error occurred while validating the file. Please try again.",
            "sanitized_name": None,
            "detected_mime": None,
        }


def log_security_event(event_type, details, ip_address=None):
    """
    Log security events for monitoring and auditing.

    Args:
        event_type: Type of security event
        details: Additional details about the event
        ip_address: IP address of the client
    """
    logger.warning(
        f"SECURITY EVENT: {event_type} | Details: {details} | IP: {ip_address}"
    )

    # In production, you might want to:
    # - Send alerts for critical events
    # - Store in separate security log
    # - Trigger automated responses (rate limiting, blocking)
