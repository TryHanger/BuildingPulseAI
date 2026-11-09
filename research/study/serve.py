"""Serve exactly the local participant assets. The coordinator folder is never served."""
import argparse
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def serve(public, port):
    permitted = {"/study.js": "text/javascript", "/study.css": "text/css"}
    pages = [path for path in (public / "cards").iterdir() if re.fullmatch(r"[0-9a-f]{20}\.html", path.name)]
    if len(pages) != 18:
        raise ValueError("Expected 18 study pages")
    for page in pages:
        permitted[f"/cards/{page.name}"] = "text/html"
    assets = {url: ((public / url[1:]).read_bytes(), mime) for url, mime in permitted.items()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            entry = assets.get(urlsplit(self.path).path)
            status = 200 if entry else 404
            content, mime = entry or (b"Not found", "text/plain")
            self.send_response(status)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(content)

        do_HEAD = do_GET

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path)
    parser.add_argument("--port", type=int, default=18161)
    serve(**vars(parser.parse_args()))
