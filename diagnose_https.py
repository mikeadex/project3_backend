import os
import sys
import socket

def check_https_redirect():
    # Check system-wide proxy settings
    print("System Proxy Settings:")
    print(f"HTTP_PROXY: {os.getenv('HTTP_PROXY', 'Not set')}")
    print(f"HTTPS_PROXY: {os.getenv('HTTPS_PROXY', 'Not set')}")
    
    # Check browser extensions or system settings
    print("\nPossible HTTPS Forcing Sources:")
    print("1. Check browser settings for automatic HTTPS redirect")
    print("2. Disable HTTPS-Everywhere browser extension")
    print("3. Check system-wide proxy or VPN settings")
    
    # Network socket test
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('localhost', 8000))
        print(f"\nSocket Connection to localhost:8000: {'Success' if result == 0 else 'Failed'}")
    except Exception as e:
        print(f"Socket test error: {e}")

if __name__ == '__main__':
    check_https_redirect()