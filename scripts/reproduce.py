"""Every required stage is explicit; all never conceals an open proof gate."""
import argparse
import json
import shutil
import sys
from common import ROOT, command, new_run, finish


def stage(name, args):
    if name == "doctor":
        from doctor import run
        return run()
    if name in ("models", "mutations", "witnesses"):
        from run_models import run
        return run(args.profile, args.timeout, name == "mutations", name == "witnesses")
    if name == "case-study":
        from run_scenarios import run
        return run()
    if name == "paper":
        from build_paper import run
        return run()
    if name == "conformance":
        from verification.trace_conformance import run
        return run()
    if name == "analyze":
        from experiments.analysis import run
        return run()
    if name == "package":
        from package_artifact import run
        return run()
    if name == "claims":
        from check_claims import run
        return run()
    if name == "proofs":
        from run_proofs import run
        return run(args.timeout)
    directory, manifest = new_run(name)
    if name == "baseline":
        missing = ["original explorers", "original reports", "original reviews", "original publisher files"]
        return finish(directory, manifest, "inconclusive", {"missing": missing,
                      "snapshot": "verification/baseline", "reason": "not present in supplied checkout"})
    if name == "spec-check":
        results = []
        for path in sorted((ROOT / "specification").glob("*.tla")):
            result, output = command([__import__("common").java() or "java", "-cp", ROOT / ".tools/tla2tools.jar",
                                      "-DTLA-Library=" + str(ROOT / "specification"),
                                      "tla2sany.SANY", path], directory, path.stem)
            if "Semantic errors" in output or "Fatal errors" in output or "Parse Error" in output:
                result["status"] = "failed"
            results.append(result)
        return finish(directory, manifest, "passed" if all(r["status"] == "passed" for r in results) else "failed", results)
    if name == "tests":
        result, _ = command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], directory, "tests")
        return finish(directory, manifest, result["status"], result)
    raise ValueError(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["doctor", "baseline", "spec-check", "proofs", "models", "mutations", "witnesses",
                                        "case-study", "conformance", "analyze", "paper", "package", "tests", "claims", "all"])
    parser.add_argument("--profile", choices=["smoke", "core"], default="smoke")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if args.stage == "all":
        outcomes = {}
        for name in ("doctor", "baseline", "spec-check", "proofs", "models", "mutations", "witnesses", "tests", "case-study",
                     "conformance", "analyze", "claims", "paper", "package"):
            try:
                outcomes[name] = stage(name, args)
            except Exception as error:
                outcomes[name] = 1
                print(name, repr(error), file=sys.stderr)
        print(json.dumps(outcomes, indent=2))
        return int(any(outcomes.values()))
    return stage(args.stage, args)


if __name__ == "__main__":
    raise SystemExit(main())
