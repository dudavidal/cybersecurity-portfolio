import os
import uuid

_node_name = os.environ.get("NODE_NAME", "")
PEER_ID = (_node_name + "_" + str(uuid.uuid4())) if _node_name else str(uuid.uuid4())

UDP_DISCOVERY_PORT = int(os.environ.get("UDP_DISCOVERY_PORT", 9999))
TCP_PORT           = int(os.environ.get("TCP_PORT", 6000))

BROADCAST_ADDR = os.environ.get("BROADCAST_ADDR", "255.255.255.255")

DISCOVERY_INTERVAL = int(os.environ.get("DISCOVERY_INTERVAL", 5))
PEER_TIMEOUT       = int(os.environ.get("PEER_TIMEOUT", 15))
POLL_INTERVAL      = int(os.environ.get("POLL_INTERVAL", 3))

HTTP_PORT_BASE = int(os.environ.get("HTTP_PORT_BASE", 8000))
HTTP_PORT      = HTTP_PORT_BASE

SYNC_FOLDER = os.environ.get("SYNC_FOLDER", "sync_folder")

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 60000))
