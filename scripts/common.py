from pathlib import Path
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def hashes():
    result = {}
    for folder in ("src", "specification", "proofs", "models", "scripts", "experiments", "verification", "case-study", "tests"):
        for path in sorted((ROOT / folder).rglob("*")):
            if (path.is_file() and path.suffix in {".py", ".tla", ".cfg", ".json", ".yaml"}
                    and not any(part in {"__pycache__", ".tlacache", "states", "baseline"} for part in path.parts)
                    and path.name != "proof-status.json"):
                result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for filename in ("docs/paper/main.tex", "docs/paper/references.bib", "docs/paper/sn-jnl.cls",
                     "docs/paper/sn-mathphys-num.bst", "environment/toolchain.lock.json",
                     "environment/Dockerfile.proofs", "pyproject.toml", "requirements.lock"):
        path = ROOT / filename
        if path.is_file():
            result[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else "unavailable"


def new_run(kind, configuration=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S") + "-" + kind + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / "results" / "raw" / run_id
    directory.mkdir(parents=True)
    manifest = {"run_id": run_id, "utc": now.isoformat(), "kind": kind,
                "commit": git("rev-parse", "HEAD"), "git_status": git("status", "--short"),
                "source_sha256": hashes(), "configuration": configuration or {},
                "python": sys.version, "os": platform.platform(), "processor": platform.processor(),
                "logical_cpus": os.cpu_count(), "memory_limit": "not imposed on Python",
                "command": sys.argv, "status": "inconclusive"}
    with zipfile.ZipFile(directory / "sources.zip", "w", zipfile.ZIP_DEFLATED) as snapshot:
        for filename in manifest["source_sha256"]:
            snapshot.write(ROOT / filename, filename)
    manifest["sources_zip_sha256"] = hashlib.sha256((directory / "sources.zip").read_bytes()).hexdigest()
    write_json(directory / "manifest.json", manifest)
    return directory, manifest


def finish(directory, manifest, status, results):
    manifest["status"] = status
    write_json(directory / "results.json", results)
    manifest["results_sha256"] = hashlib.sha256((directory / "results.json").read_bytes()).hexdigest()
    write_json(directory / "manifest.json", manifest)
    print(str(directory.relative_to(ROOT)) + ": " + status)
    return 0 if status == "passed" else 1


def command(args, directory, name, timeout=90, cwd=ROOT):
    started = time.monotonic()
    try:
        p = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        result = {"command": [str(a) for a in args], "cwd": str(Path(cwd).relative_to(ROOT)),
                  "exit_code": p.returncode, "status": "passed" if p.returncode == 0 else "failed"}
        output = p.stdout + "\n" + p.stderr
    except subprocess.TimeoutExpired as error:
        def decode(v):
            return v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v or ""
        result = {"command": list(map(str, args)), "exit_code": None, "status": "timeout"}
        output = decode(error.stdout) + decode(error.stderr)
    except OSError as error:
        result = {"command": list(map(str, args)), "exit_code": None, "status": "skipped"}
        output = str(error)
    result["elapsed_seconds"] = time.monotonic() - started
    result["timeout_seconds"] = timeout
    result["log"] = name + ".log"
    (directory / result["log"]).write_text(output, encoding="utf-8")
    return result, output


def java():
    candidate = os.environ.get("VGC_JAVA") or shutil.which("java")
    if not candidate and platform.system() == "Windows":
        local = Path("C:/Program Files/PaperCut MF Client/runtime/jre/bin/java.exe")
        if local.is_file():
            candidate = str(local)
    return candidate
