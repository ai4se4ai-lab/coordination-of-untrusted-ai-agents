import hashlib
import json
import re
from common import ROOT, hashes


def run():
    paper = (ROOT / "docs/paper/main.tex").read_text(encoding="utf-8")
    bibliography = (ROOT / "docs/paper/references.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\{([^,]+)", bibliography))
    cited = {key.strip() for group in re.findall(r"\\cite\w*\{([^}]+)\}", paper) for key in group.split(",")}
    errors = ["missing bibliography key: " + key for key in sorted(cited - keys)]
    labels = re.findall(r"\\label\{([^}]+)\}", paper)
    refs = re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", paper)
    errors += ["missing label: " + label for label in set(refs)-set(labels)]
    errors += ["duplicate label: " + label for label in set(labels) if labels.count(label) > 1]
    for phrase in ("end-to-end machine-verified implementation", "all central obligations have been discharged"):
        if phrase in paper:
            errors.append("unsupported wording: " + phrase)
    path = ROOT / "results/processed/document-service-v1/summary.json"
    if path.is_file():
        summary = json.loads(path.read_text())
        current_hashes = hashes()
        for kind, info in summary["sources"].items():
            directory = ROOT / "results/raw" / info["run"]
            for filename, field in (("results.json", "results_sha256"), ("manifest.json", "manifest_sha256")):
                if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != info[field]:
                    errors.append("stale processed evidence: " + kind)
            manifest = json.loads((directory / "manifest.json").read_text())
            prefixes = ("specification/", "models/") if kind in ("models", "mutations", "witnesses") else ("proofs/", "specification/") if kind == "proofs" else ("src/", "experiments/scenarios.py", "case-study/document-service/scenarios/") if kind == "case-study" else ("verification/trace_conformance.py",) if kind == "conformance" else ("tests/", "src/")
            for file, digest in manifest["source_sha256"].items():
                if file == "proofs/proof-status.json":
                    continue
                if file.startswith(prefixes) and (not (ROOT / file).is_file() or hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != digest):
                    errors.append("stale source for " + kind + ": " + file)
            previous_paths = {file for file in manifest["source_sha256"] if file.startswith(prefixes) and file != "proofs/proof-status.json"}
            current_paths = {file for file in current_hashes if file.startswith(prefixes) and file != "proofs/proof-status.json"}
            if current_paths != previous_paths:
                errors.append("changed relevant source inventory for " + kind)
        try:
            region = paper.split("% BEGIN GENERATED TLC RESULTS", 1)[1].split("% END GENERATED TLC RESULTS", 1)[0]
            from experiments.paper_results import model_table, render
            detail_path = ROOT / "results/processed/document-service-v1/detailed-results.json"
            detail = json.loads(detail_path.read_text())
            ledger = json.loads((ROOT / "results/processed/document-service-v1/paper-number-manifest.json").read_text())
            if hashlib.sha256(detail_path.read_bytes()).hexdigest() != ledger["detailed_region"]["data_sha256"]:
                errors.append("detailed results data differs from evidence ledger")
            if hashlib.sha256((ROOT / ledger["detailed_region"]["derivation"]).read_bytes()).hexdigest() != ledger["detailed_region"]["derivation_sha256"]:
                errors.append("detailed result generator changed since analysis")
            if region.strip() != model_table(detail):
                errors.append("generated TeX table differs from raw reports")
            region = paper.split("% BEGIN GENERATED DETAILED RESULTS", 1)[1].split("% END GENERATED DETAILED RESULTS", 1)[0].strip()
            if region != render(detail):
                errors.append("generated detailed figures/tables/discussion differ from evidence data")
            for file, digest in detail["inputs_sha256"].items():
                if not (ROOT / file).is_file() or hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != digest:
                    errors.append("changed detailed evidence input: " + file)
            from experiments.analysis import campaign_prose
            prose = paper.split("% BEGIN GENERATED CAMPAIGN SUMMARY", 1)[1].split("% END GENERATED CAMPAIGN SUMMARY", 1)[0].strip()
            if prose != campaign_prose(summary):
                errors.append("generated campaign prose differs from processed evidence")
        except (IndexError, KeyError):
            errors.append("missing generated evidence regions")
    else:
        errors.append("missing processed summary")
    print("\n".join(errors) if errors else "Citations, labels and processed evidence checks passed. Central proof gate remains incomplete.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(run())
