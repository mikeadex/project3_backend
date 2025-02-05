import os
import sys
import socket
import ssl
import http.client

def check_https_redirect():
    print("HTTPS Redirect Diagnostic Tool")
    print("=" * 40)
    
    # Check environment variables
    print("\n1. Environment Variables:")
    print(f"DJANGO_DEBUG: {os.getenv('DJANGO_DEBUG', 'Not set')}")
    print(f"SECURE_SSL_REDIRECT: {os.getenv('SECURE_SSL_REDIRECT', 'Not set')}")
    
    # Network socket test
    print("\n2. Network Socket Test:")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('localhost', 8000))
        print(f"Socket Connection to localhost:8000: {'Success' if result == 0 else 'Failed'}")
    except Exception as e:
        print(f"Socket test error: {e}")
    
    # HTTP Connection Test
    print("\n3. HTTP Connection Test:")
    try:
        conn = http.client.HTTPConnection('localhost', 8000, timeout=5)
        conn.request('GET', '/api/diagnose/')
        response = conn.getresponse()
        print(f"HTTP Request Status: {response.status}")
        print(f"Response Headers: {response.getheaders()}")
    except Exception as e:
        print(f"HTTP connection error: {e}")
    
    # SSL/TLS Context Information
    print("\n4. SSL/TLS Context:")
    try:
        context = ssl.create_default_context()
        with socket.create_connection(('localhost', 8000)) as sock:
            with context.wrap_socket(sock, server_hostname='localhost') as secure_sock:
                print("SSL/TLS Connection Successful")
                print(f"Protocol: {secure_sock.version()}")
    except Exception as e:
        print(f"SSL/TLS connection error: {e}")

if __name__ == '__main__':
    check_https_redirect()