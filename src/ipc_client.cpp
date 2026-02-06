/*
  IPC Client Implementation
  =========================

  Cross-platform socket communication for C++ to Python service.
  Uses TCP localhost on all platforms for compatibility (Unix domain sockets
  not available on Windows).
*/

#include "bruce/knowledge/ipc_client.hpp"

#include <cstring>
#include <sstream>
#include <chrono>
#include <thread>

// Platform-specific includes
#ifdef _WIN32
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "ws2_32.lib")
  #define SOCKET_ERROR_VAL SOCKET_ERROR
  #define CLOSE_SOCKET closesocket
  typedef int socklen_t;
#else
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #include <fcntl.h>
  #include <poll.h>
  #include <cerrno>
  #define SOCKET_ERROR_VAL -1
  #define CLOSE_SOCKET close
  typedef int SOCKET;
  const int INVALID_SOCKET = -1;
#endif

namespace bruce::knowledge {

// ============================================================
// Initialization (Windows-specific)
// ============================================================

#ifdef _WIN32
class WinsockInitializer {
public:
  WinsockInitializer() {
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
      throw SocketError("WSAStartup failed");
    }
  }
  ~WinsockInitializer() {
    WSACleanup();
  }
};

static WinsockInitializer g_winsock_init;
#endif

// ============================================================
// UnixSocketClient Implementation (TCP-based for cross-platform)
// ============================================================

UnixSocketClient::~UnixSocketClient() {
  disconnect();
}

void UnixSocketClient::connect() {
  if (sock_fd != INVALID_SOCKET) {
    return;  // Already connected
  }

  // Parse socket_path format: "localhost:5555" or "/tmp/socket.sock" (for compatibility)
  std::string host = "127.0.0.1";
  uint16_t port = 5555;

  if (socket_path.find(':') != std::string::npos) {
    // Format: host:port
    size_t colon_pos = socket_path.rfind(':');
    host = socket_path.substr(0, colon_pos);
    try {
      port = static_cast<uint16_t>(std::stoi(socket_path.substr(colon_pos + 1)));
    } catch (...) {
      throw SocketError("Invalid port in socket path: " + socket_path);
    }
  } else if (socket_path.find("/") != std::string::npos || socket_path.find("\\") != std::string::npos) {
    // Unix socket path format - use default localhost:port
    // (Unix sockets converted to TCP for cross-platform compatibility)
  }

  // Create TCP socket
  sock_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (sock_fd == INVALID_SOCKET) {
    throw SocketError("Failed to create socket");
  }

  // Prepare address
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);

  if (inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
    CLOSE_SOCKET(sock_fd);
    sock_fd = INVALID_SOCKET;
    throw SocketError("Invalid host: " + host);
  }

  // Attempt connection with retry logic
  auto deadline = std::chrono::system_clock::now() +
                  std::chrono::milliseconds(connect_timeout_ms);

  int attempt = 0;
  while (std::chrono::system_clock::now() < deadline) {
    int result = ::connect(sock_fd, (struct sockaddr*)&addr, sizeof(addr));

    if (result == 0) {
      // Connected successfully
      return;
    }

    attempt++;
    if (attempt < 5 && std::chrono::system_clock::now() < deadline) {
      // Retry after short delay
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    } else {
      break;
    }
  }

  CLOSE_SOCKET(sock_fd);
  sock_fd = INVALID_SOCKET;
  throw SocketError("Failed to connect to " + host + ":" + std::to_string(port));
}

void UnixSocketClient::disconnect() {
  if (sock_fd != INVALID_SOCKET) {
    CLOSE_SOCKET(sock_fd);
    sock_fd = INVALID_SOCKET;
  }
}

bool UnixSocketClient::is_connected() const {
  return sock_fd != INVALID_SOCKET;
}

void UnixSocketClient::send_data(const char* data, size_t size) {
  if (sock_fd == INVALID_SOCKET) {
    throw SocketError("Socket not connected");
  }

  size_t sent = 0;

  while (sent < size) {
    int n = send(sock_fd, data + sent, static_cast<int>(size - sent), 0);

    if (n == SOCKET_ERROR_VAL) {
      throw SocketError("Send failed");
    }

    if (n == 0) {
      throw SocketError("Connection closed by server");
    }

    sent += n;
  }
}

size_t UnixSocketClient::receive_data(char* buffer, size_t max_size) {
  if (sock_fd == INVALID_SOCKET) {
    throw SocketError("Socket not connected");
  }

  // Set receive timeout
  int timeout_ms = static_cast<int>(read_timeout_ms);
#ifdef _WIN32
  if (setsockopt(sock_fd, SOL_SOCKET, SO_RCVTIMEO, (char*)&timeout_ms, sizeof(timeout_ms)) < 0) {
    throw SocketError("Failed to set socket timeout");
  }
#else
  struct timeval tv;
  tv.tv_sec = timeout_ms / 1000;
  tv.tv_usec = (timeout_ms % 1000) * 1000;
  if (setsockopt(sock_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0) {
    throw SocketError("Failed to set socket timeout");
  }
#endif

  int n = recv(sock_fd, buffer, static_cast<int>(max_size), 0);

  if (n == SOCKET_ERROR_VAL) {
    throw SocketError("Receive failed or timeout");
  }

  if (n == 0) {
    throw SocketError("Connection closed by server");
  }

  return static_cast<size_t>(n);
}

std::string UnixSocketClient::send_request(const std::string& request) {
  // Connect if needed
  if (!is_connected()) {
    connect();
  }

  // Send request
  send_data(request.c_str(), request.size());

  // Receive response
  char buffer[65536];
  size_t received = receive_data(buffer, sizeof(buffer));

  return std::string(buffer, received);
}

// ============================================================
// SearchServiceClient Implementation
// ============================================================

std::string SearchServiceClient::search(const std::string& query_text) {
  ensure_connected();

  // Build JSON request
  std::ostringstream oss;
  oss << "{\"query_text\": \"" << query_text << "\"}";
  std::string request = oss.str();

  // Send and receive
  std::string response = socket.send_request(request);

  return response;
}

std::optional<std::string> SearchServiceClient::search_safe(const std::string& query_text) {
  try {
    return search(query_text);
  } catch (const SocketError& e) {
    if (auto_reconnect) {
      try {
        socket.disconnect();
        socket.connect();
        return search(query_text);
      } catch (...) {
        return std::nullopt;
      }
    }
    return std::nullopt;
  }
}

void SearchServiceClient::reconnect() {
  socket.disconnect();
  socket.connect();
}

void SearchServiceClient::ensure_connected() {
  if (!socket.is_connected()) {
    socket.connect();
  }
}

}  // namespace bruce::knowledge
