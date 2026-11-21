"""Start the local workbench without a console after Windows sign-in."""

from pathlib import Path
import os
import runpy
import sys


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
log_path = ROOT / "logs" / "workbench-autostart.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
log = log_path.open("a", encoding="utf-8", buffering=1)
sys.stdout = log
sys.stderr = log
sys.path.insert(0, str(ROOT / "workbench"))
sys.argv = [str(ROOT / "workbench" / "server.py"), "--no-browser"]
runpy.run_path(sys.argv[0], run_name="__main__")
