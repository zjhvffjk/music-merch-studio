"""Run the existing workbench behind its protected web entry."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    backend = subprocess.Popen([sys.executable, str(ROOT / 'workbench/server.py'), '--no-browser'], cwd=ROOT)
    try:
        for _ in range(90):
            if backend.poll() is not None:
                raise RuntimeError('Workbench failed to start')
            try:
                urllib.request.urlopen('http://127.0.0.1:8765/api/ping', timeout=2).close()
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError('Workbench startup timed out')
        import uvicorn
        uvicorn.run('deploy.web:app', host='0.0.0.0', port=8080, proxy_headers=True, forwarded_allow_ips='*', access_log=False)
    finally:
        backend.terminate()
        try:
            backend.wait(timeout=10)
        except subprocess.TimeoutExpired:
            backend.kill()


if __name__ == '__main__':
    main()
