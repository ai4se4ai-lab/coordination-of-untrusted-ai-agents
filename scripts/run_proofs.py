import json
import re
import shutil
from common import ROOT, command, new_run, finish, write_json


def run(timeout=90):
    directory, manifest = new_run("proofs", {"scope": "scoped lemmas; central Core invariant and forward simulation remain open"})
    native = shutil.which("tlapm")
    image = "vgc-tlaps:local"
    prefix = [native] if native else ["docker", "run", "--rm", "--network", "none",
             "--mount", f"type=bind,source={ROOT},target=/work", "-w", "/work/proofs", image,
             "/work/.tools/tlapm/bin/tlapm"]
    tool, config = command(prefix + ["--config"], directory, "backends", timeout=20)
    results = []
    for module in ("Budget", "ControllerSafety", "StructuralKernelProofs", "DocumentPolicyProofs"):
        file = str(ROOT / "proofs" / (module + ".tla")) if native else module + ".tla"
        include = str(ROOT / "specification") if native else "/work/specification"
        result, output = command(prefix + ["--strict", "--cleanfp", "--timing", "-I", include, file],
                                 directory, module, timeout=timeout)
        result["module"] = module
        result["scope"] = "scoped lemma; not full controller verification"
        counts = re.findall(r"(\d+) obligations?", output)
        result["reported_obligation_counts"] = counts
        total = re.search(r"(\d+) total obligations", output)
        proved = re.search(r"All (\d+) obligations proved", output)
        result["total_obligations"] = int(total.group(1)) if total else None
        result["proved_obligations"] = int(proved.group(1)) if proved else None
        result["omitted_obligations"] = 0 if result["status"] == "passed" and proved else None
        results.append(result)
    report = {"central_gate": "incomplete", "backend_config": tool, "lemmas": results,
              "remaining": ["Core Init/Next inductive invariant", "history/episode counting proof",
                            "asynchronous/atomic action correspondence", "kernel interface connection",
                            "policy interpreter trace induction"]}
    write_json(ROOT / "proofs/proof-status.json", {"run": directory.relative_to(ROOT).as_posix(), **report})
    # A successful scoped lemma run cannot close the central gate.
    return finish(directory, manifest, "inconclusive", report)
