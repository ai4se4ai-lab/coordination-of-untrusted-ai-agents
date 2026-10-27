import json
import re
import sys
from common import ROOT, java, command, new_run, finish


def run(profile="smoke", timeout=60, mutations=False, witnesses=False):
    matrix = json.loads((ROOT / "models/matrix.yaml").read_text())
    selected = [m for m in matrix if (m.get("witness", False) if witnesses else
                m.get("mutant", False) if mutations else
                not m.get("mutant", False) and not m.get("witness", False) and (profile == "core" or m["profile"] == "smoke"))]
    directory, manifest = new_run("witnesses" if witnesses else "mutations" if mutations else "models", {"profile": profile, "matrix": selected})
    results = []
    for item in selected:
        config = ROOT / item["config"]
        result, log = command([java() or "java", "-Xmx768m", "-cp", ROOT / ".tools/tla2tools.jar",
                               "-DTLA-Library=" + str(ROOT / "specification"), "tlc2.TLC",
                               "-workers", "1", "-cleanup", "-noGenerateSpecTE", "-coverage", "1",
                               "-metadir", ROOT / "tmp/tlc" / item["id"],
                               "-config", config, ROOT / item["module"]],
                              directory, item["id"], timeout=timeout)
        result.update({"id": item["id"], "expected": item["expected"], "heap_mb": 768})
        counts = re.findall(r"([\d,]+) states generated, ([\d,]+) distinct states found", log)
        if counts:
            result["generated_states"], result["distinct_states"] = [int(x.replace(",", "")) for x in counts[-1]]
        violation = re.search(r"Invariant (\w+) is violated", log)
        if violation:
            result["status"] = "counterexample"
            result["violated"] = violation.group(1)
        result["expectation_met"] = (item["expected"] == "counterexample" and result["status"] == "counterexample"
                                     and result["violated"] == item.get("invariant", "Safety")) or (
                                     item["expected"] == "passed" and result["status"] == "passed"
                                     and "Model checking completed. No error has been found." in log)
        results.append(result)
        print(item["id"], result["status"], result.get("distinct_states", ""), flush=True)
    return finish(directory, manifest, "passed" if all(r["expectation_met"] for r in results) else "failed", results)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else "smoke"))
