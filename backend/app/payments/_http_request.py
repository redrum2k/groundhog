"""Disposable stdlib-only HTTP child. Parent owns the elapsed limit and reaping.

Input/output are anonymous pipes, never argv, files or diagnostics. This process
cannot sign or persist; it performs exactly one direct POST, without redirects,
proxy discovery or retries. Do not import the application or load configuration.
"""

import base64
import http.client
import json
import sys
from urllib.parse import unquote, urlsplit


def request():
    url, method, params = json.load(sys.stdin)
    parsed = urlsplit(url)
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port)
    headers = {"Content-Type": "application/json", "Connection": "close"}
    if parsed.username is not None:
        credentials = unquote(parsed.username) + ":" + unquote(parsed.password or "")
        headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        connection.request(
            "POST",
            path,
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}),
            headers,
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError
        # Bound both child buffering and the parent's final JSON decode. These RPCs
        # request individual blocks/receipts/state, never bulk chain history.
        limit = 4 * 1024 * 1024
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError
        decoded = json.loads(body)
        if decoded.get("id") != 1 or "error" in decoded or "result" not in decoded:
            raise ValueError
        json.dump(decoded["result"], sys.stdout)
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        request()
    except Exception:
        sys.exit(1)  # Parent emits only a structural, capability-free error.
