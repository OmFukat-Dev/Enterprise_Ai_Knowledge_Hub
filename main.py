# main.py — LAUNCH SCRIPT
from dotenv import load_dotenv
import subprocess
import threading
import time
import webbrowser
import os

load_dotenv()  # Load .env before anything else

STREAMLIT_ONLY = os.getenv("STREAMLIT_ONLY", "1") == "1"


# ── Streamlit subprocess ──────────────────────────────────────────────────────
def start_streamlit():
    subprocess.Popen([
        "streamlit", "run", "frontend/dashboard.py",
        "--server.port=8501",
        "--server.address=127.0.0.1",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--server.maxUploadSize=200",
        "--server.fileWatcherType=none",
    ])


# Bug 10 Fix: Thread was spawned at module top-level — any "import main" in tests
# or other code would launch a Streamlit process. Moved inside __main__ guard.
if __name__ == '__main__':
    # Start Streamlit in background thread
    threading.Thread(target=start_streamlit, daemon=True).start()
    time.sleep(3)  # Give Streamlit time to start
    webbrowser.open("http://127.0.0.1:8501")

    if not STREAMLIT_ONLY:
        try:
            import uvicorn
            from app import app as api_app  # noqa: F401
            uvicorn.run(
                app=api_app,
                host="0.0.0.0",
                port=8000,
                reload=False,
                log_level="info",
            )
        except Exception as exc:
            print(f"[main.py] FastAPI startup failed (non-fatal): {exc}")
    else:
        # Keep main thread alive while Streamlit runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
