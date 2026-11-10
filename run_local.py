"""Local development launcher for the stateless AirOps FastAPI services."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_BODY = 22 * 1024 * 1024  # 20 MiB upload cap plus multipart/request overhead.
SERVICE_PORT_BASE = int(os.getenv("AIR_OPS_SERVICE_PORT_BASE", "8001"))
SERVICES = {
    "/api/source/": ("services.source_service.main", SERVICE_PORT_BASE),
    "/api/contracts/": ("services.contract_service.main", SERVICE_PORT_BASE + 1),
    "/api/blocks/": ("services.block_service.main", SERVICE_PORT_BASE + 2),
}


class Gateway(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def _proxy(self) -> None:
        route = next(((prefix, port) for prefix, (_, port) in SERVICES.items() if self.path.startswith(prefix)), None)
        if route is None:
            self.send_error(404)
            return
        prefix, port = route
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if length < 0 or length > MAX_BODY:
            self.send_error(413, "Request exceeds the 20 MB prototype limit")
            return
        body = self.rfile.read(length) if length else None
        target = "http://127.0.0.1:" + str(port) + "/" + self.path[len(prefix):]
        request = urllib.request.Request(
            target,
            data=body,
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            method=self.command,
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (urllib.error.URLError, TimeoutError, OSError):
            self.send_error(503, "AirOps service is starting or unavailable")

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_GET()


def start_services() -> list[subprocess.Popen[bytes]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    children = []
    try:
        for module, port in SERVICES.values():
            children.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", module + ":app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT,
                env=env,
            ))
    except Exception:
        stop_services(children)
        raise
    return children


def stop_services(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def wait_for_services(children: list[subprocess.Popen[bytes]]) -> None:
    pending = set(SERVICES.values())
    deadline = time.monotonic() + 30
    while pending and time.monotonic() < deadline:
        for module, port in tuple(pending):
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A FastAPI service exited during startup.")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5):
                    pending.remove((module, port))
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
        time.sleep(0.15)
    if pending:
        raise RuntimeError("Timed out waiting for FastAPI services: " + ", ".join(str(port) for _, port in pending))


def main() -> None:
    children: list[subprocess.Popen[bytes]] = []
    port = int(os.getenv("AIR_OPS_PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Gateway, directory=str(WEB)))
    server.daemon_threads = True
    serve_thread: Thread | None = None
    try:
        children = start_services()
        wait_for_services(children)
        print(f"AirOps is running at http://localhost:{port} (Ctrl+C to stop).", flush=True)
        serve_thread = Thread(target=server.serve_forever, daemon=True)
        serve_thread.start()
        while any(child.poll() is None for child in children):
            time.sleep(1)
        raise RuntimeError("A FastAPI service stopped unexpectedly.")
    except KeyboardInterrupt:
        print("Stopping AirOps services…", flush=True)
    finally:
        if serve_thread and serve_thread.is_alive():
            server.shutdown()
            serve_thread.join(timeout=5)
        server.server_close()
        stop_services(children)


if __name__ == "__main__":
    main()
