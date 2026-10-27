"""Derive paper data from raw reports, preserving failures in selected campaigns."""
import hashlib
import json
from pathlib import Path
from scripts.common import ROOT, write_json


def latest(kind):
    runs = sorted((ROOT / "results/raw").glob("*-" + kind + "-*"))
    if not runs:
        return None
    return runs[-1]


def campaign_prose(summary):
    enumeration = (f"The policy-language campaign enumerated {summary['policy_tables_enumerated']:,} typed tables across both policy settings, "
                   f"and exercised all {summary['policy_event_words']:,} event words of length at most six for the strict table. ") if summary["policy_tables_enumerated"] is not None and summary["policy_event_words"] is not None else "The finite-language campaign is incomplete; no completed enumeration is claimed. "
    return (f"The scripted campaign passed {summary['scenario_passes']} of {summary['scenarios']} predefined scenarios. "
            f"The separate checker admitted {summary['trace_passes']} of {summary['recorded_traces']} recorded traces "
            f"and rejected {summary['corruptions_rejected']} deliberately corrupted traces. "
            + enumeration +
            f"The separate nonvacuity campaign produced {summary['reachability_witnesses']} expected shortest reachability witnesses. "
            f"The scoped TLAPS run discharged {summary['scoped_proved_obligations']} generated obligations across the reported lemma modules; "
            "this count includes supporting obligations and does not discharge the central controller invariant or refinement theorem.")


def run():
    processed = ROOT / "results/processed/document-service-v1"
    sources, reports = {}, {}
    for kind in ("models", "mutations", "witnesses", "case-study", "conformance", "proofs", "tests"):
        directory = latest(kind)
        if directory is None:
            raise ValueError("missing campaign " + kind)
        path = directory / "results.json"
        reports[kind] = json.loads(path.read_text())
        sources[kind] = {"run": directory.name, "results_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "manifest_sha256": hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()}
    summary = {
        "sources": sources,
        "model_configurations": len(reports["models"]),
        "model_passes": sum(r["status"] == "passed" for r in reports["models"]),
        "model_nonpasses": [r for r in reports["models"] if r["status"] != "passed"],
        "mutant_configurations": len(reports["mutations"]),
        "mutant_counterexamples": sum(r["status"] == "counterexample" for r in reports["mutations"]),
        "mutant_survivors": [r["id"] for r in reports["mutations"] if r["status"] == "passed"],
        "reachability_witnesses": sum(r["expectation_met"] for r in reports["witnesses"]),
        "scenarios": len(reports["case-study"]),
        "scenario_passes": sum(r["status"] == "passed" for r in reports["case-study"]),
        "recorded_traces": len(reports["conformance"]["traces"]),
        "trace_passes": sum(r["status"] == "passed" for r in reports["conformance"]["traces"]),
        "corruptions_rejected": sum(r["rejected"] for r in reports["conformance"]["corruptions"]),
        "central_proof_gate": reports["proofs"]["central_gate"],
        "scoped_proof_modules": [{"module": r["module"], "status": r["status"]} for r in reports["proofs"]["lemmas"]],
        "scoped_proved_obligations": sum(r.get("proved_obligations") or 0 for r in reports["proofs"]["lemmas"]),
        "policy_tables_enumerated": next((r.get("metrics", {}).get("policy_tables_enumerated") for r in reports["case-study"] if r["id"] == "S28" and r["status"] == "passed"), None),
        "policy_event_words": next((r.get("metrics", {}).get("policy_event_words") for r in reports["case-study"] if r["id"] == "S28" and r["status"] == "passed"), None),
        "interpretation": "Deterministic checks; no measured LLM performance or statistical sample claims",
    }
    conformance_manifest = json.loads((ROOT / "results/raw" / sources["conformance"]["run"] / "manifest.json").read_text())
    if conformance_manifest["configuration"]["source_run"] != sources["case-study"]["run"]:
        raise ValueError("conformance report refers to a different case-study campaign")
    write_json(processed / "summary.json", summary)
    # Data and native plots are generated into one TeX source, never \input.
    cells = []
    for kind in ("models", "mutations"):
        for row in reports[kind]:
            cells.append({"table": "tab:exploration" if kind == "models" else "tab:mutation-detail", "row": row["id"], "source": sources[kind],
                          "fields": ["distinct_states", "generated_states", "elapsed_seconds"] if kind == "models" else ["distinct_states", "generated_states", "elapsed_seconds", "status", "violated"],
                          "derived_data": "detailed-results.json#" + kind})
    paper = ROOT / "docs/paper/main.tex"
    source = paper.read_text(encoding="utf-8")
    start, end = "% BEGIN GENERATED CAMPAIGN SUMMARY", "% END GENERATED CAMPAIGN SUMMARY"
    if start in source:
        prefix, tail = source.split(start, 1)
        _, suffix = tail.split(end, 1)
        prose = campaign_prose(summary)
        source = prefix + start + "\n" + prose + "\n" + end + suffix
    paper.write_text(source, encoding="utf-8")
    from experiments.paper_results import derive, update_paper
    detail = derive(reports, sources, summary)
    write_json(processed / "detailed-results.json", detail)
    update_paper(paper, detail)
    write_json(processed / "paper-number-manifest.json", {"cells": cells,
               "detailed_region": {"data": "results/processed/document-service-v1/detailed-results.json",
                                   "data_sha256": hashlib.sha256((processed / "detailed-results.json").read_bytes()).hexdigest(),
                                   "derivation": "experiments/paper_results.py",
                                   "derivation_sha256": hashlib.sha256((ROOT / "experiments/paper_results.py").read_bytes()).hexdigest(),
                                   "figures": {"fig:state-space": "models:distinct_states,generated_states",
                                               "fig:shortest-paths": "mutations,witnesses:shortest_actions",
                                               "fig:scenario-heatmap": "scenarios:channels",
                                               "fig:request-deltas": "request_interventions:requests_after"},
                                   "tables": {"tab:exploration": "models", "tab:proof-results": "proofs.lemmas",
                                              "tab:proof-development": "historical_proofs", "tab:mutation-detail": "mutations",
                                              "tab:witness-detail": "witnesses", "tab:scenario-results": "scenarios",
                                              "tab:request-interventions": "request_interventions", "tab:validation-domains": "policy_metrics,tests,conformance",
                                              "tab:negative-controls": "tests,conformance.corruptions", "tab:campaign-history": "history",
                                              "tab:clean-reproductions": "clean_runs"},
                                   "inputs_sha256": detail["inputs_sha256"]},
               "summary_numbers": {key: {"value": value, "derivation": "experiments/analysis.py", "sources": sources}
                                   for key, value in summary.items() if isinstance(value, int)}})
    print(processed.relative_to(ROOT))
    return int(bool(summary["model_nonpasses"]) or summary["scenario_passes"] != summary["scenarios"] or
               summary["trace_passes"] != summary["recorded_traces"])
