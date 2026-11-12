# Engine 02: Multi-Process Index Manager (Operating Systems)

Manages process isolation, IPC hot-reloading, atomic index swaps, and crash recovery across two independent OS processes.

## Files
- manager.py: Spawns and monitors Indexer & Query Handler processes
- ipc_server.py: Query Handler process serving queries and listening for IPC RELOAD signals
- indexer_worker.py: Indexer process writing temp files, validating, and atomically replacing data/active_index.json
- engine_hooks.py: Integration adapter for Engine 03 (SQLite) and Engine 01 (BM25)

## Run Demo
python E02_Multiprocess_Index_Manager/manager.py
