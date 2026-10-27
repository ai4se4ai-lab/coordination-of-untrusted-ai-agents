"""Reproduce the artifact from a fresh external directory and compare outcomes.

Uses installed host tools and the documented proof image, not a fresh OS.
The complete plan remains incomplete even when this reproducibility check passes.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from common import ROOT, new_run, write_json, finish


def run():
    artifact = ROOT / "dist/vgc-artifact-0.1.0.zip"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    clean = Path(tempfile.mkdtemp(prefix="vgc-reproduce-"))
    directory, manifest = new_run("clean-reproduction", {
        "archive_sha256": digest, "extracted_directory": str(clean),
        "isolation": "fresh directory outside checkout; installed host/container tools; hashed tool downloads"})
    try:
        with zipfile.ZipFile(artifact) as archive:
            for name in archive.namelist():
                if not (clean / name).resolve().is_relative_to(clean.resolve()):
                    raise ValueError("unsafe archive path")
            archive.extractall(clean)
        checksums = json.loads((clean / "ARTIFACT-CHECKSUMS.json").read_text())
        for name, expected in checksums.items():
            if hashlib.sha256((clean / name).read_bytes()).hexdigest() != expected:
                raise ValueError("checksum mismatch: " + name)
        commands = []
        for label, args in (("bootstrap", [sys.executable, "scripts/bootstrap_tools.py"]),
                            ("all", [sys.executable, "scripts/reproduce.py", "all", "--profile", "core", "--timeout", "60"])):
            started = time.monotonic()
            process = subprocess.Popen(args, cwd=clean, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace")
            lines = []
            with (directory / (label + ".log")).open("w", encoding="utf-8") as log:
                for line in process.stdout:
                    lines.append(line)
                    log.write(line)
                    log.flush()
                    print(line.rstrip(), flush=True)
            code = process.wait()
            commands.append({"command": args, "cwd": str(clean), "exit_code": code,
                             "elapsed_seconds": time.monotonic()-started, "log": label + ".log"})
            if label == "bootstrap" and code != 0:
                raise ValueError("clean bootstrap failed")
            if label == "all":
                output = "".join(lines)
                outcomes = json.loads(output[output.rfind("\n{")+1:])
        summary = json.loads((clean / "results/processed/document-service-v1/summary.json").read_text())
        original = json.loads((ROOT / "results/processed/document-service-v1/summary.json").read_text())
        keys = ["model_passes", "mutant_counterexamples", "mutant_survivors", "reachability_witnesses",
                "scenario_passes", "trace_passes", "corruptions_rejected", "scoped_proved_obligations",
                "policy_tables_enumerated", "policy_event_words", "central_proof_gate"]
        matches = all(summary[k] == original[k] for k in keys)
        expected = {stage: (1 if stage == "baseline" or stage == "proofs" and
                           original["central_proof_gate"] != "complete" else 0) for stage in outcomes}
        report = {"archive_sha256": digest, "extracted_directory": str(clean),
                  "checksums_verified": len(checksums), "commands": commands,
                  "stage_exit_codes": outcomes, "scientific_outcomes_match": matches,
                  "comparison": {k: summary[k] for k in keys},
                  "scope": "fresh directory with installed host/container tools; not fresh OS or full verification"}
        write_json(ROOT / "dist/clean-reproduction.json", report)
        return finish(directory, manifest, "passed" if matches and outcomes == expected else "failed", report)
    except Exception as error:
        return finish(directory, manifest, "failed", {"error": repr(error), "archive_sha256": digest,
                                                     "extracted_directory": str(clean)})


if __name__ == "__main__":
    raise SystemExit(run())
