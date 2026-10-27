import hashlib
from pathlib import Path
import zipfile
from common import ROOT, write_json


def run():
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / "vgc-artifact-0.1.0.zip"
    members = []
    excluded_snapshots = []
    for folder in ("src", "specification", "proofs", "models", "case-study", "experiments", "verification", "tests", "scripts", "docs", "environment", ".github", "results", "reviews"):
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or any(part in {"__pycache__", ".tlacache", "states"} for part in path.parts):
                continue
            if path.name == "sources.zip":
                with zipfile.ZipFile(path) as snapshot:
                    if any(".tlacache/" in n or "__pycache__/" in n for n in snapshot.namelist()):
                        excluded_snapshots.append(path.relative_to(ROOT).as_posix())
                        continue
            relative = path.relative_to(ROOT).as_posix()
            evidence_log = relative.startswith(("results/", "verification/baseline/", "reviews/evidence/"))
            if path.suffix in {".pyc", ".aux", ".log", ".out", ".blg", ".bbl"} and not evidence_log:
                continue
            if path.suffix == ".pdf" and path.name not in {"main.pdf"}:
                continue
            members.append(path)
    for name in ("README.md", "LICENSE", "CITATION.cff", ".gitignore", ".gitattributes", ".dockerignore", "pyproject.toml", "requirements.lock"):
        if (ROOT / name).is_file():
            members.append(ROOT / name)
    checksums = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in members:
            archive.write(p, p.relative_to(ROOT).as_posix())
        import json
        archive.writestr("ARTIFACT-CHECKSUMS.json", json.dumps(checksums, indent=2, sort_keys=True))
        archive.writestr("EXCLUDED-DEVELOPMENT-SNAPSHOTS.json", json.dumps({"reason": "early source inventory captured transient proof caches; final scientific snapshots exclude them", "files": excluded_snapshots}, indent=2))
    with zipfile.ZipFile(output) as archive:
        for name, digest in checksums.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("archive checksum failure: " + name)
        if any(name.startswith((".git/", ".tools/", ".env")) for name in archive.namelist()):
            raise ValueError("excluded material in bundle")
    write_json(dist / "artifact-manifest.json", {"file": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
               "members": len(members), "central_proof_gate": "incomplete", "archive_checksums_verified": True})
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
