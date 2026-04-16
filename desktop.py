"""
Olive Pizza — desktop application (native window + local server).

Run from project folder:
    python desktop.py

Requires:
    pip install pywebview
    MySQL running and DATABASE_URL / config (same as web app).

Optional EXE (PyInstaller, from this folder):
    pyinstaller --noconfirm --onedir --name OlivePizza ^
      --add-data "templates;templates" --add-data "static;static" ^
      --collect-all flask --collect-all sqlalchemy desktop.py
"""

from __future__ import annotations

import socket
import sys
import threading
import time


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _wait_server(host: str, port: int, attempts: int = 60) -> bool:
    for _ in range(attempts):
        try:
            socket.create_connection((host, port), timeout=0.25)
            return True
        except OSError:
            time.sleep(0.1)
    return False


def _run_flask(app, host: str, port: int) -> None:
    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def main() -> None:
    try:
        import webview
    except ImportError:
        print("Missing dependency. Install with: python -m pip install pywebview", file=sys.stderr)
        sys.exit(1)

    # Single Flask app instance (same as `python app.py`)
    from app import app

    host = "127.0.0.1"
    port = _free_port()
    url = f"http://{host}:{port}/"

    thread = threading.Thread(
        target=_run_flask,
        args=(app, host, port),
        daemon=True,
        name="flask-server",
    )
    thread.start()

    if not _wait_server(host, port):
        print("Could not start local web server.", file=sys.stderr)
        sys.exit(1)

    webview.create_window(
        "Olive Pizza — Operations",
        url,
        width=1366,
        height=768,
        resizable=True,
        min_size=(960, 600),
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
