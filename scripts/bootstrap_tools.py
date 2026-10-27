"""Download exact hashed tool artifacts locally; never install host system tools."""
from pathlib import Path
import hashlib
import json
import tarfile
import urllib.request
import shutil
from common import ROOT


def main():
    lock = json.loads((ROOT / "environment/toolchain.lock.json").read_text())
    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    for name, filename in (("tla2tools.jar", "tla2tools.jar"), ("tlapm", "tlapm.tar.gz")):
        record = lock[name]
        path = tools / filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            temporary = tools / (filename + ".download")
            with urllib.request.urlopen(record["url"], timeout=60) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("upstream artifact changed: " + name + "; refusing unpinned bytes")
            temporary.replace(path)
        print(name, record["sha256"])
    if not (tools / "tlapm/bin/tlapm").is_file():
        with tarfile.open(tools / "tlapm.tar.gz") as archive:
            archive.extractall(tools, filter="data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
