import json
import time
import traceback
from common import ROOT, new_run, finish, write_json
from experiments.scenarios import run_scenario


def run():
    definitions = json.loads((ROOT / "case-study/document-service/scenarios/campaign.json").read_text())
    directory, manifest = new_run("case-study", {"definitions": definitions, "protocol": "experiments/protocol.yaml"})
    results = []
    for definition in definitions:
        started = time.monotonic()
        result = dict(definition)
        try:
            c = run_scenario(definition["id"])
            result["status"] = "passed"
            result["requests"] = len(c.history)
            result["episodes_allocated_upper_bound"] = c.nonce
            result["semantic_commits"] = sum(e["outcome"] == "committed" for e in c.events)
            result["publications"] = sum(e["outcome"] == "published" for e in c.events)
            result["rejections"] = sum(e["outcome"] == "rejected" for e in c.events)
            result["metrics"] = getattr(c, "experiment_metrics", {})
            trace_file = definition["id"] + ".trace.json"
            write_json(directory / trace_file, {"initial": c.initial, "events": c.events})
            result["trace"] = trace_file
        except Exception:
            result["status"] = "failed"
            result["error"] = traceback.format_exc()
        result["elapsed_seconds"] = time.monotonic() - started
        results.append(result)
        print(result["id"], result["status"], flush=True)
    return finish(directory, manifest, "passed" if all(r["status"] == "passed" for r in results) else "failed", results)
