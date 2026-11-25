"""Review/apply only EnzyMind's existing Nginx timeouts. Apply requires root."""
import argparse
import difflib
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--apply", action="store_true", help="Back up, validate, and reload Nginx")
parser.add_argument("--config", type=Path, default=Path("/etc/nginx/sites-enabled/webapps.conf"))
args = parser.parse_args()
target = args.config.resolve()
original = target.read_text()
blocks = list(re.finditer(r"(?m)^    location /enzymind/ \{[^{}]*\}", original))
if len(blocks) != 1:
    raise SystemExit("Expected exactly one simple /enzymind/ location. Review this config manually.")
block = blocks[0]
replacement = block.group()
for name in ("proxy_send_timeout", "proxy_read_timeout"):
    replacement, count = re.subn(rf"({name}\s+)\d+s;", rf"\g<1>3780s;", replacement)
    if count != 1:
        raise SystemExit(f"Expected one {name} in the EnzyMind location; no changes made.")
updated = original[:block.start()] + replacement + original[block.end():]
if updated == original:
    print("EnzyMind Nginx timeouts are already configured.")
    raise SystemExit(0)
print("".join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                                fromfile=str(target), tofile=str(target) + " (proposed)")))
if not args.apply:
    print("Review only. Apply with sudo python3 scripts/configure_nginx_timeout.py --apply")
    raise SystemExit(0)
if os.geteuid() != 0:
    raise SystemExit("Administrator rights required. No changes made.")
subprocess.run(["nginx", "-t"], check=True)
backup = target.with_name(target.name + ".enzymind-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
shutil.copy2(target, backup)
try:
    target.write_text(updated)
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["nginx", "-s", "reload"], check=True)
except Exception:
    target.write_text(original)
    raise
print(f"Updated and reloaded EnzyMind timeouts. Backup: {backup}")
