# main.py — FINAL INTEGRATED VERSION
from dotenv import load_dotenv
import subprocess
import threading
import time
import webbrowser
import os

load_dotenv()  # Load .env

# Start Streamlit in thread
def start_streamlit():
    subprocess.Popen([
        "streamlit", "run", "frontend/dashboard.py",
        "--server.port=8501",
        "--server.address=127.0.0.1",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--server.maxUploadSize=200",
        "--server.fileWatcherType=none"
    ])

# Launch
threading.Thread(target=start_streamlit, daemon=True).start()
time.sleep(3)  # Wait for Streamlit
webbrowser.open("http://127.0.0.1:8501")

if __name__ == '__main__':
    streamlit_only = os.getenv("STREAMLIT_ONLY", "0") == "1"
    if not streamlit_only:
        try:
            import uvicorn
            from app import app as api_app
            uvicorn.run("main:api_app", host="0.0.0.0", port=8000, reload=False, log_level="info")
        except Exception:
            pass
    else:
        # Keep main thread alive for Streamlit
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
