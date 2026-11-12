import json
import os
import tempfile
from multiprocessing.connection import Client
import engine_hooks

INDEX_PATH = "data/active_index.json"
IPC_ADDRESS = ("localhost", 6000)
AUTH_KEY = b"careindex_secret"

def validate_index(file_path: str) -> bool:
    try:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return "version" in data and isinstance(data.get("terms"), dict) and len(data["terms"]) > 0
    except Exception:
        return False

def build_and_publish_index(version: int, simulate_crash: bool = False):
    os.makedirs("data", exist_ok=True)
    print(f"[Indexer PID {os.getpid()}] Starting index build v{version}...")

    fd, temp_path = tempfile.mkstemp(dir="data", prefix="index_build_", suffix=".tmp")
    
    try:
        payload = engine_hooks.fetch_from_db_and_build_index(version)

        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file, indent=2)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        if simulate_crash:
            print(f"[Indexer PID {os.getpid()}] SIMULATING CRASH before validation/swap!")
            os._exit(1)

        if not validate_index(temp_path):
            raise ValueError("Index validation failed!")

        os.replace(temp_path, INDEX_PATH)
        print(f"[Indexer PID {os.getpid()}] Atomically published v{version} -> {INDEX_PATH}")

        with Client(IPC_ADDRESS, authkey=AUTH_KEY) as conn:
            conn.send("RELOAD")
            ack = conn.recv()
            print(f"[Indexer PID {os.getpid()}] Query Handler response: {ack}")

    except Exception as e:
        print(f"[Indexer PID {os.getpid()}] Build aborted: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
