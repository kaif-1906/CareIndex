import json
import os
import threading
import time
from multiprocessing.connection import Listener

INDEX_PATH = "data/active_index.json"
IPC_ADDRESS = ("localhost", 6000)
AUTH_KEY = b"careindex_secret"

class QueryHandler:
    def __init__(self):
        self.index_data = {}
        self.lock = threading.Lock()
        self.load_index()

    def load_index(self):
        if not os.path.exists(INDEX_PATH):
            print("[QueryHandler] No active index found yet. Waiting...")
            return
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            with self.lock:
                self.index_data = new_data
            print(f"[QueryHandler] Loaded index version: {self.index_data.get('version')} ({len(self.index_data.get('terms', {}))} terms)")
        except Exception as e:
            print(f"[QueryHandler] Failed to load index, keeping previous version: {e}")

    def search(self, term):
        with self.lock:
            version = self.index_data.get("version", "NONE")
            results = self.index_data.get("terms", {}).get(term.lower(), [])
        return {"index_version": version, "term": term, "matches": results}

def listen_for_ipc(handler: QueryHandler):
    with Listener(IPC_ADDRESS, authkey=AUTH_KEY) as listener:
        print(f"[QueryHandler PID {os.getpid()}] Listening for IPC signals...")
        while True:
            with listener.accept() as conn:
                msg = conn.recv()
                if msg == "RELOAD":
                    print("[QueryHandler] IPC 'RELOAD' signal received! Swapping in-memory index...")
                    handler.load_index()
                    conn.send("ACK_RELOADED")
