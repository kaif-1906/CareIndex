import multiprocessing
import time
import ipc_server
import indexer_worker

def run_query_process():
    import os, threading
    os.makedirs("data", exist_ok=True)
    handler = ipc_server.QueryHandler()
    t = threading.Thread(target=ipc_server.listen_for_ipc, args=(handler,), daemon=True)
    t.start()
    while True:
        time.sleep(2)
        print(f"  [SEARCH LIVE] {handler.search('fever')}")

def run_indexer_process():
    time.sleep(1)
    indexer_worker.build_and_publish_index(version=1)
    time.sleep(4)
    indexer_worker.build_and_publish_index(version=2)
    time.sleep(4)
    indexer_worker.build_and_publish_index(version=3, simulate_crash=True)

if __name__ == "__main__":
    p_query = multiprocessing.Process(target=run_query_process, name="QueryHandlerProc")
    p_indexer = multiprocessing.Process(target=run_indexer_process, name="IndexerProc")

    p_query.start()
    p_indexer.start()

    p_indexer.join()
    print(f"\n[Manager] Indexer exit code: {p_indexer.exitcode} (Non-zero means crashed!)")
    print(f"[Manager] Is Query Handler still alive? {p_query.is_alive()}")

    time.sleep(5)
    p_query.terminate()
