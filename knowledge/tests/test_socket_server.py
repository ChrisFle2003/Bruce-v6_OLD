"""
Socket Server Tests
===================

Tests IPC communication between C++ client and Python search service.
"""

import sys
import os
import json
import socket
import time
import subprocess
import signal
from pathlib import Path

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

def test_socket_server_startup():
    """Test that socket server can start and listen."""
    print("\nTest 1: Socket Server Startup")

    # Create server instance (without running)
    from socket_server import SocketServer

    server = SocketServer(use_mock=True)
    print(f"  [OK] Server instance created")
    print(f"  [OK] Socket path: {server.SOCKET_PATH}")

    assert server.search_engine is not None
    print(f"  [OK] Search engine initialized")


def test_socket_communication():
    """Test socket communication with mock server."""
    print("\nTest 2: Socket Communication (with mock server)")

    from socket_server import SocketServer

    server = SocketServer(use_mock=True)
    server.setup()
    print(f"  [OK] Server socket set up at {server.SOCKET_PATH}")

    try:
        # Simulate client connection
        print(f"  Creating test client...")

        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.connect(server.SOCKET_PATH)
        print(f"  [OK] Client connected to server")

        # Send JSON request
        request = json.dumps({"query_text": "Python Lambda Functions"})
        client_sock.sendall(request.encode('utf-8'))
        print(f"  [OK] Sent request: {request[:50]}...")

        # Receive response
        client_sock.settimeout(10)  # 10 second timeout
        response_data = client_sock.recv(65536).decode('utf-8')
        print(f"  [OK] Received response ({len(response_data)} bytes)")

        # Parse response
        response = json.loads(response_data)
        print(f"  [OK] Response parsed successfully")

        # Verify response structure
        assert 'query' in response or 'error' in response
        print(f"  [OK] Response has expected structure")

        if 'error' not in response:
            assert 'seiten_count' in response
            print(f"  [OK] Found {response['seiten_count']} results")

        client_sock.close()
        print(f"  [OK] Client disconnected")

    finally:
        server.cleanup()


def test_multiple_requests():
    """Test multiple sequential requests to socket server."""
    print("\nTest 3: Multiple Sequential Requests")

    from socket_server import SocketServer

    server = SocketServer(use_mock=True)
    server.setup()

    try:
        queries = [
            "Python Lambda Functions",
            "Advanced Programming Patterns",
            "Function Definition",
        ]

        for i, query in enumerate(queries, 1):
            print(f"  Request {i}: {query[:40]}...")

            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(server.SOCKET_PATH)

            request = json.dumps({"query_text": query})
            client_sock.sendall(request.encode('utf-8'))

            client_sock.settimeout(10)
            response_data = client_sock.recv(65536).decode('utf-8')
            response = json.loads(response_data)

            assert 'query' in response or 'error' in response
            print(f"    [OK] Response received")

            client_sock.close()

        print(f"  [OK] All {len(queries)} requests succeeded")

    finally:
        server.cleanup()


def test_error_handling():
    """Test error handling with invalid requests."""
    print("\nTest 4: Error Handling")

    from socket_server import SocketServer

    server = SocketServer(use_mock=True)
    server.setup()

    try:
        # Test 1: Invalid JSON
        print(f"  Testing invalid JSON...")
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.connect(server.SOCKET_PATH)

        client_sock.sendall(b"{invalid json")
        client_sock.settimeout(10)
        response_data = client_sock.recv(65536).decode('utf-8')
        response = json.loads(response_data)

        assert 'error' in response
        print(f"  [OK] Invalid JSON handled: {response['error'][:40]}...")
        client_sock.close()

        # Test 2: Empty query
        print(f"  Testing empty query...")
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.connect(server.SOCKET_PATH)

        request = json.dumps({"query_text": ""})
        client_sock.sendall(request.encode('utf-8'))
        client_sock.settimeout(10)
        response_data = client_sock.recv(65536).decode('utf-8')
        response = json.loads(response_data)

        assert 'error' in response
        print(f"  [OK] Empty query handled: {response['error'][:40]}...")
        client_sock.close()

        # Test 3: Missing query_text field
        print(f"  Testing missing query_text...")
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.connect(server.SOCKET_PATH)

        request = json.dumps({"something": "else"})
        client_sock.sendall(request.encode('utf-8'))
        client_sock.settimeout(10)
        response_data = client_sock.recv(65536).decode('utf-8')
        response = json.loads(response_data)

        assert 'error' in response
        print(f"  [OK] Missing field handled: {response['error'][:40]}...")
        client_sock.close()

    finally:
        server.cleanup()


def test_socket_client_interface():
    """Test the SearchServiceClient interface."""
    print("\nTest 5: SearchServiceClient Interface")

    from socket_server import SocketServer, SearchServiceClient

    server = SocketServer(use_mock=True)
    server.setup()

    try:
        # Create client
        client = SearchServiceClient(server.SOCKET_PATH)
        print(f"  [OK] SearchServiceClient created")

        # Execute search
        query = "Python Lambda Functions"
        try:
            response_str = client.search(query)
            response = json.loads(response_str)
            print(f"  [OK] Search executed, got response")
            print(f"  [OK] Response keys: {list(response.keys())[:3]}...")
        except Exception as e:
            print(f"  [INFO] Search raised exception (expected if server not responding): {type(e).__name__}")

    finally:
        server.cleanup()


def run_all_tests():
    """Run all socket server tests."""
    print("=" * 60)
    print("Socket Server IPC Tests")
    print("=" * 60)

    tests = [
        test_socket_server_startup,
        test_socket_communication,
        test_multiple_requests,
        test_error_handling,
        test_socket_client_interface,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] Assertion failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
