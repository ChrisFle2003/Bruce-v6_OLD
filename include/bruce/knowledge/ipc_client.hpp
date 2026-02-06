/*
  IPC Client for Hierarchical Knowledge Service
  ==============================================

  Provides C++ interface to socket communication with Python search service.
  Uses TCP localhost for cross-platform compatibility (Unix domain sockets
  not available on Windows).

  Architecture:
  - Client-side (C++) connects to Python socket server via TCP (localhost:5555)
  - Protocol: JSON request/response over TCP
  - Timeout-based error handling with automatic retry
  - Automatic reconnection on failure

  Usage:
    // Parse socket_path as "host:port" (default: "127.0.0.1:5555")
    SearchServiceClient client("127.0.0.1:5555");
    std::string response = client.search("query text");
*/

#pragma once

#include <string>
#include <cstdint>
#include <optional>
#include <stdexcept>

// Platform-specific socket type
#ifdef _WIN32
  typedef unsigned long long SOCKET;
  const SOCKET INVALID_SOCKET = ~0ULL;
#else
  typedef int SOCKET;
  const int INVALID_SOCKET = -1;
#endif

namespace bruce::knowledge {

/*
  Socket Client Exception
  =======================

  Thrown when socket communication fails.
*/

class SocketError : public std::runtime_error {
public:
  explicit SocketError(const std::string& message)
      : std::runtime_error(message) {}
};

/*
  Unix Domain Socket Client
  =========================

  Low-level socket communication for IPC.
*/

class UnixSocketClient {
private:
  std::string socket_path;
  SOCKET sock_fd = INVALID_SOCKET;
  uint32_t connect_timeout_ms = 5000;
  uint32_t read_timeout_ms = 10000;
  uint32_t write_timeout_ms = 5000;

public:
  /*
    Constructor

    Args:
      path: Socket connection string in format "host:port" (default: "127.0.0.1:5555")
            or Unix socket path format (auto-converted to TCP)
  */
  explicit UnixSocketClient(const std::string& path)
      : socket_path(path) {}

  ~UnixSocketClient();

  /*
    Connect to socket server

    Throws:
      SocketError if connection fails
  */
  void connect();

  /*
    Disconnect from socket server
  */
  void disconnect();

  /*
    Send JSON request and receive JSON response

    Args:
      request: JSON string to send

    Returns:
      JSON response string

    Throws:
      SocketError on communication failure
  */
  std::string send_request(const std::string& request);

  /*
    Check if currently connected

    Returns:
      true if socket is connected and healthy
  */
  bool is_connected() const;

  /*
    Set connection timeout (milliseconds)
  */
  void set_connect_timeout(uint32_t ms) { connect_timeout_ms = ms; }

  /*
    Set read timeout (milliseconds)
  */
  void set_read_timeout(uint32_t ms) { read_timeout_ms = ms; }

  /*
    Set write timeout (milliseconds)
  */
  void set_write_timeout(uint32_t ms) { write_timeout_ms = ms; }

private:
  /*
    Internal: Send data with timeout

    Args:
      data: Data to send
      size: Size in bytes

    Throws:
      SocketError on write failure
  */
  void send_data(const char* data, size_t size);

  /*
    Internal: Receive data with timeout

    Args:
      buffer: Buffer to receive into
      max_size: Maximum bytes to receive

    Returns:
      Number of bytes received

    Throws:
      SocketError on read failure
  */
  size_t receive_data(char* buffer, size_t max_size);
};

/*
  High-Level Search Client
  ========================

  User-friendly interface to search service.
*/

class SearchServiceClient {
private:
  UnixSocketClient socket;
  bool auto_reconnect = true;

public:
  explicit SearchServiceClient(const std::string& socket_path)
      : socket(socket_path) {}

  /*
    Execute hierarchical search

    Args:
      query_text: Text to search for

    Returns:
      JSON response with results

    Throws:
      SocketError if search fails
  */
  std::string search(const std::string& query_text);

  /*
    Execute search with detailed response handling

    Args:
      query_text: Text to search for

    Returns:
      Parsed response as JSON object (or nullopt on error)
  */
  std::optional<std::string> search_safe(const std::string& query_text);

  /*
    Enable/disable automatic reconnection on failure
  */
  void set_auto_reconnect(bool enabled) { auto_reconnect = enabled; }

  /*
    Reconnect to service if disconnected
  */
  void reconnect();

private:
  void ensure_connected();
};

}  // namespace bruce::knowledge
