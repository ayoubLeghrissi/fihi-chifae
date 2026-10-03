import json, time, subprocess, sys, os, signal, socket, urllib.request

def _free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p

def test_ping_and_catalog_smoke():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(port)], cwd=os.path.dirname(os.path.dirname(__file__)))
    try:
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/ping", timeout=1) as r:
                    assert r.status == 200
                    data=json.loads(r.read()); assert data["status"]=="ok"
                    break
            except Exception:
                time.sleep(0.3)
        else:
            assert False, "server did not start"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/catalog", timeout=2) as r:
            assert r.status == 200
            data=json.loads(r.read()); assert "categories" in data
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()
