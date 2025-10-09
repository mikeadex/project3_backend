# Backend Security Setup Guide

## Required Python Package: python-magic

The `file_security.py` module requires `python-magic` for deep MIME type inspection.

### Installation

#### 1. Install libmagic (system library)

**macOS:**

```bash
brew install libmagic
```

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install libmagic1
```

**CentOS/RHEL:**

```bash
sudo yum install file-libs
```

**Windows:**

```bash
# Download from: https://github.com/julian-r/python-magic#windows
# Or use: pip install python-magic-bin (includes binaries)
```

#### 2. Install Python package

```bash
cd /Users/michaeladeleye/Documents/Coding/ella/Ella-backend
pip install python-magic
```

#### 3. Update requirements.txt

Add to `requirements.txt`:

```
python-magic==0.4.27
```

### Verification

Test the installation:

```bash
python manage.py shell
```

```python
import magic
print(magic.from_file('/path/to/test.pdf', mime=True))
# Should output: 'application/pdf'
```

### Integration Steps

1. **Update guest_views.py**:

```python
from .file_security import validate_uploaded_file, log_security_event

# In guest_analyze action (around line 150):
file = request.FILES['file']

# Add comprehensive validation BEFORE existing checks
validation = validate_uploaded_file(file)
if not validation['valid']:
    ip_address = self.get_client_ip(request)
    log_security_event('upload_rejected', validation['error'], ip_address)
    return Response({
        'error': validation['error']
    }, status=status.HTTP_400_BAD_REQUEST)

# Use sanitized filename
file.name = validation['sanitized_name']

# Continue with existing code...
```

2. **Update cv_writer/views.py** (authenticated upload):

```python
from ai_cv_parser.file_security import validate_uploaded_file

# In upload endpoint:
validation = validate_uploaded_file(request.FILES['file'])
if not validation['valid']:
    return Response({
        'error': validation['error']
    }, status=status.HTTP_400_BAD_REQUEST)
```

### Testing

Test the security with curl:

```bash
# Valid file (should work)
curl -X POST http://localhost:8000/api/cv-parser/guest/analyze/ \
  -F "file=@test_resume.pdf"

# Invalid file (should be rejected)
curl -X POST http://localhost:8000/api/cv-parser/guest/analyze/ \
  -F "file=@malware.exe"

# Spoofed file (exe renamed to pdf - should be detected)
cp malware.exe fake.pdf
curl -X POST http://localhost:8000/api/cv-parser/guest/analyze/ \
  -F "file=@fake.pdf"
```

### Troubleshooting

**Error: "magic" module not found**

```bash
pip install python-magic
```

**Error: "failed to find libmagic"**

```bash
# macOS
brew install libmagic
export DYLD_LIBRARY_PATH=/usr/local/lib

# Linux
sudo apt-get install libmagic1
sudo ldconfig
```

**Error: "bad magic number"**

```bash
# Update libmagic database
# macOS
brew upgrade libmagic

# Linux
sudo apt-get update
sudo apt-get install --reinstall libmagic1
```

### Optional: ClamAV Integration

For virus scanning (production environments):

```bash
# Install ClamAV
sudo apt-get install clamav clamav-daemon
pip install pyclamd

# Update virus definitions
sudo freshclam
```

Add to `file_security.py`:

```python
import pyclamd

def scan_for_viruses(file):
    """Scan file with ClamAV"""
    try:
        cd = pyclamd.ClamdUnixSocket()
        scan_result = cd.scan_stream(file.read())
        file.seek(0)

        if scan_result:
            return {
                'valid': False,
                'error': 'Virus detected in file'
            }
        return {'valid': True}
    except:
        return {'valid': True}  # Don't block if scanner unavailable
```

### Production Deployment

1. Install dependencies on server
2. Enable security logging
3. Set up monitoring alerts
4. Configure rate limiting
5. Test with malware samples
6. Set up automated backups

### Support

For issues, check:

- [python-magic GitHub](https://github.com/ahupp/python-magic)
- Django logs: `logs/django.log`
- Security events: `grep "SECURITY EVENT" logs/django.log`
