"""Container start hook. Python, not a shell script, so Windows CRLF checkouts still run."""

import os
import shutil
import sys
from pathlib import Path

claims_path = Path(os.environ["CLAIMS_PATH"])
claims_path.parent.mkdir(parents=True, exist_ok=True)
if not claims_path.exists():
    shutil.copy("/app/data/mock_claims.json", claims_path)

command = sys.argv[1:] or [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
]
os.execvp(command[0], command)
