"""
Hierarchical Knowledge Socket Server
====================================

Unix Domain Socket server for IPC communication between Bruce C++ core
and Python search service.

Protocol:
- Request: JSON with query_text and optional constraints
- Response: JSON with search results or error
- Connection: Unix domain socket at /tmp/bruce_hierarchical_search.sock
"""

import socket
import json
import os
import sys
import signal
import logging
from typing import Dict, Any
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Import search service
sys.path.insert(0, os.path.dirname(__file__))
from hierarchical_search_mvp import HierarchicalSearchMVP


class SocketServer:
    """Unix Domain Socket server for hierarchical knowledge service."""

    SOCKET_PATH = "/tmp/bruce_hierarchical_search.sock"
    BUFFER_SIZE = 65536
    MAX_CONNECTIONS = 10

    def __init__(self, db_host="localhost", db_port=5433, use_mock=False):
        """
        Initialize socket server.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            use_mock: Use mock embeddings (for testing)
        """
        self.db_host = db_host
        self.db_port = db_port
        self.use_mock = use_mock

        # Create search engine
        try:
            self.search_engine = HierarchicalSearchMVP(
                db_host=db_host,
                db_port=db_port,
                use_mock_embeddings=use_mock
            )
            logger.info("Search engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize search engine: {e}")
            raise

        self.socket = None
        self.running = False

    def cleanup(self):
        """Clean up socket file and close socket."""
        if self.socket:
            self.socket.close()
            logger.info("Socket closed")

        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
            logger.info(f"Socket file removed: {self.SOCKET_PATH}")

    def setup(self):
        """Set up socket server."""
        # Clean up any existing socket
        self.cleanup()

        # Create socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.SOCKET_PATH)
        self.socket.listen(self.MAX_CONNECTIONS)

        # Set permissions (world-readable/writable for testing)
        os.chmod(self.SOCKET_PATH, 0o777)

        logger.info(f"Socket server listening on {self.SOCKET_PATH}")
        logger.info(f"Max connections: {self.MAX_CONNECTIONS}")

    def handle_client(self, conn: socket.socket, addr) -> None:
        """
        Handle single client connection.

        Args:
            conn: Client socket connection
            addr: Client address
        """
        try:
            # Receive request
            logger.info("Client connected")
            data = conn.recv(self.BUFFER_SIZE).decode('utf-8')

            if not data:
                logger.warning("Empty request received")
                return

            logger.info(f"Received {len(data)} bytes")

            # Parse JSON request
            try:
                request = json.loads(data)
                logger.info(f"Request: {request.get('query_text', '')[:50]}...")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                error_response = json.dumps({"error": "Invalid JSON in request"})
                conn.sendall(error_response.encode('utf-8'))
                return

            # Execute search
            query_text = request.get('query_text', '')

            if not query_text:
                logger.warning("Empty query_text")
                error_response = json.dumps({"error": "query_text is required"})
                conn.sendall(error_response.encode('utf-8'))
                return

            # Perform search
            logger.info("Executing search...")
            results = self.search_engine.search(query_text)

            # Send response
            response_json = json.dumps(results)
            response_bytes = response_json.encode('utf-8')

            logger.info(f"Sending {len(response_bytes)} bytes")
            conn.sendall(response_bytes)

            logger.info("Response sent successfully")

        except Exception as e:
            logger.error(f"Error handling client: {e}")
            try:
                error_response = json.dumps({"error": str(e)})
                conn.sendall(error_response.encode('utf-8'))
            except:
                pass  # Connection may be closed

        finally:
            try:
                conn.close()
                logger.info("Client disconnected")
            except:
                pass

    def run(self):
        """Run socket server (main loop)."""
        self.setup()
        self.running = True

        logger.info("Starting socket server...")
        logger.info(f"Listening on: {self.SOCKET_PATH}")

        try:
            while self.running:
                try:
                    logger.info("Waiting for connections...")
                    conn, addr = self.socket.accept()

                    # Handle client in main thread (could use threading for parallel)
                    self.handle_client(conn, addr)

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received")
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"Error in accept loop: {e}")

        finally:
            self.running = False
            self.cleanup()
            logger.info("Socket server stopped")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Hierarchical Knowledge Socket Server"
    )
    parser.add_argument(
        "--db-host",
        default="localhost",
        help="PostgreSQL host (default: localhost)"
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=5433,
        help="PostgreSQL port (default: 5433)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock embeddings (for testing without Ollama)"
    )
    parser.add_argument(
        "--socket",
        default="/tmp/bruce_hierarchical_search.sock",
        help="Socket path (default: /tmp/bruce_hierarchical_search.sock)"
    )

    args = parser.parse_args()

    # Update socket path if specified
    SocketServer.SOCKET_PATH = args.socket

    # Create and run server
    server = SocketServer(
        db_host=args.db_host,
        db_port=args.db_port,
        use_mock=args.mock
    )

    # Handle signals gracefully
    def signal_handler(sig, frame):
        logger.info(f"Signal {sig} received, shutting down...")
        server.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run server
    try:
        server.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
