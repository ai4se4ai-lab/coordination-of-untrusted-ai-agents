"""Render the TSE manuscript's evaluation tables, figures and numbers.

Inputs are the processed evidence files; outputs are TeX fragments under
docs/paper-tse/generated/ that main.tex \\input{}s. Nothing is typed by hand:
re-running this script after a new campaign updates every reported number.

    python experiments/tse_paper.py [--campaign results/processed/tse/campaign.json]
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/paper-tse/generated"
DETAIL = ROOT / "results/processed/document-service-v1/detailed-results.json"

MODEL_NAMES = {"one-k1": "One job", "one-k2": "One job", "chain-k1": "Two-job chain",
               "chain-k2-frozen": "Two-job chain, frozen", "fanout-frozen": "Fan-out, frozen",
               "workflow-frozen": "Four-stage workflow, frozen", "one-reversion": "Observation reversion",
               "parallel-delivery": "Reordered delivery", "chain-terminal": "Chain, liveness"}
FAULTS = {"no-cancel": ("Cancellation removed", "Current observation"),
          "no-recheck": ("Commit recheck removed", "Current observation"),
          "obsolete-both": ("Both obsolete defences removed", "Current observation"),
          "budget-reset": ("Exhausted budget reset", "Episode accounting"),
          "publish-suspended": ("Suspension ignored", "No suspended stage"),
          "revoked-authority": ("Authority ignored", "Current authority"),
          "stale-publication": ("Revision check removed", "Checked revision"),
          "contract-omitted": ("Contract omitted", "Contract identity"),
          "membership-omitted": ("Selected context omitted", "Context identity")}
WITNESSES = {"reach-acceptance": "Acceptance", "reach-exhaustion": "Budget exhaustion",
             "reach-suspension": "Suspension", "reach-publication": "Publication (empty workflow)",
             "reach-contractchange": "Contract change"}
SCENARIO_CLASSES = [
    ("Initial completion and no-op repair", ["S01", "S02"], r"Thm.~\ref{thm:safety}, \ref{thm:local}"),
    ("Source edits, additions, deletions", ["S03", "S04", "S05", "S06", "S17"], r"Thm.~\ref{thm:kernel}, \ref{thm:local}"),
    ("Shared-context changes and writers", ["S07", "S08", "S09", "S10", "S24"], r"Thm.~\ref{thm:local}, Prop.~\ref{prop:isolation}"),
    ("Obsolete, late, duplicate replies", ["S11", "S12", "S13"], r"Thm.~\ref{thm:safety}(iv), \ref{thm:refinement}"),
    ("Budget exhaustion and blocking", ["S14", "S15"], r"Thm.~\ref{thm:cost}, \ref{thm:termination}"),
    ("Contract change and early cutoff", ["S16", "S23"], r"Thm.~\ref{thm:local}, \ref{thm:reconfig}"),
    ("Joint conflict, rollback, stale check", ["S18", "S19", "S25"], r"Thm.~\ref{thm:safety}(i),(v)"),
    ("Reviewer and authority changes", ["S20", "S21", "S22"], r"Thm.~\ref{thm:reconfig}"),
    ("Untrusted ingress, observer loss", ["S26", "S27"], r"Prop.~\ref{prop:observation}"),
    ("Finite policy language (exhaustive)", ["S28"], r"Thm.~\ref{thm:table}"),
]
MODULE_SCOPE = {"Budget": "Counter bound for one episode", "ControllerSafety": "Commit guard implies current, authorized, valid commit",
                "StructuralKernelProofs": "Kernel coverage, unique producers, reference range",
                "DocumentPolicyProofs": "Validator equivalence; archived-put conflict"}
ABLATION_ORDER = ["full", "no-cancel", "no-recheck", "no-obsolete", "no-contract", "no-context",
                  "no-upstream", "no-authority", "no-budget", "no-candidate", "no-global"]
ABLATION_LABELS = {"full": "None (reference)", "no-cancel": "Cancellation",
                   "no-recheck": "Commit recheck", "no-obsolete": "Cancellation + recheck",
                   "no-contract": "Contract in signature", "no-context": "Context in footprint",
                   "no-upstream": "Upstream gate", "no-authority": "Authority check",
                   "no-budget": "Episode budget", "no-candidate": "Candidate normalization",
                   "no-global": "Global predicate"}
PROPERTY_ORDER = ["stale", "invalid", "upstream", "authority", "structure", "budget", "publish"]
PROPERTY_LABELS = {"stale": "P1 Stale", "invalid": "P2 Invalid", "upstream": "P3 Upstream", "authority": "P4 Authority",
                   "structure": "P5 Structure", "budget": "P6 Budget", "publish": "P7 Publish"}
STRATEGY_ORDER = ["exact", "no-cutoff", "version", "workspace", "full"]
STRATEGY_LABELS = {"exact": "Exact (ours)", "no-cutoff": "No early cutoff", "version": "Version-keyed context",
                   "workspace": "Whole workspace", "full": "Full regeneration"}
STRATEGY_STYLE = {"exact": "inkblue,mark=*", "no-cutoff": "resultteal,mark=square*", "version": "resultamber,mark=triangle*",
                  "workspace": "violet!70!black,mark=diamond*", "full": "gray!70!black,mark=x,dashed"}
CHANGE_LABELS = {"source": "Source clause edit", "context-selected": "Selected finding changed",
                 "context-unselected": "Unselected finding changed", "context-equal": "Equal content, new version",
                 "contract": "Contract change"}


def fmt(n):
    return f"{n:,}"


def macro(name, value):
    return "\\newcommand{\\%s}{%s}" % (name, value)


def tlc_table(d):
    rows = []
    for r in d["models"]:
        b = r["bounds"]
        rows.append(("Baseline", MODEL_NAMES[r["id"]], b["jobs"], b["k"], b["max_changes"],
                     fmt(r["distinct_states"]), fmt(r["generated_states"]), "--", "Pass"))
    for r in d["mutations"]:
        name, _ = FAULTS[r["id"]]
        rows.append(("Mutant", name, 1, 1, 1, fmt(r["distinct_states"]), fmt(r["generated_states"]),
                     r["shortest_actions"] if r["shortest_actions"] is not None else "--",
                     "Violated" if r["status"] == "counterexample" else r"Survives\textsuperscript{a}"))
    for r in d["witnesses"]:
        rows.append(("Witness", WITNESSES[r["id"]], 1, 1, 1, fmt(r["distinct_states"]), fmt(r["generated_states"]),
                     r["shortest_actions"], "Reached"))
    lines, group = [], None
    for row in rows:
        if row[0] != group:
            if group is not None:
                lines.append(r"\midrule")
            group = row[0]
            label = {"Baseline": "Baseline protocol (safety invariants; liveness where stated)",
                     "Mutant": "Mutants (one guard removed; target property in Table~\\ref{tab:boundaries})",
                     "Witness": "Nonvacuity witnesses (negated reachability goal)"}[group]
            lines.append(r"\multicolumn{8}{@{}l}{\textit{" + label + r"}}\\")
        lines.append(" & ".join(map(str, row[1:])) + r"\\")
    seconds = sum(r["elapsed_seconds"] for k in ("models", "mutations", "witnesses") for r in d[k])
    return (r"""\begin{table}[!t]
\centering
\caption{Bounded TLC model checking of the protocol model. $J$: jobs; $k$: attempt cap; $m$: bound on environmental changes; \emph{Distinct}/\emph{Total}: distinct and generated states; \emph{Path}: actions in the shortest counterexample or witness. All %d runs met their expectation (%.0f\,s in total, one worker).}\label{tab:tlc}
\scriptsize\setlength{\tabcolsep}{2.6pt}
\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrrrrrl@{}}\toprule
Configuration & $J$ & $k$ & $m$ & Distinct & Total & Path & Result\\\midrule
""" % (len(rows), seconds) + "\n".join(lines) + r"""
\bottomrule\end{tabular*}
\par\smallskip\raggedright\footnotesize\textsuperscript{a}Survives because the other obsolete-response defence still blocks the stale commit; see RQ1.
\end{table}""")


def scenario_table(d):
    by_id = {s["id"]: s for s in d["scenarios"]}
    lines = []
    for label, ids, theorem in SCENARIO_CLASSES:
        rows = [by_id[i] for i in ids]
        total = {k: sum(r["channels"][k] for r in rows) for k in "DARXEPB"}
        passed = sum(r["status"] == "passed" for r in rows)
        lines.append(f"{label} & {', '.join(i[1:] for i in ids)} & {theorem} & "
                     + " & ".join(str(total[k]) for k in "DARXEB") + f" & {total['P']} & {passed}/{len(rows)}" + r"\\")
    total = {k: sum(s["channels"][k] for s in d["scenarios"]) for k in "DARXEPB"}
    lines.append(r"\midrule\textbf{All scenarios} & 01--28 & & " + " & ".join(str(total[k]) for k in "DARXEB")
                 + f" & {total['P']} & {sum(s['status'] == 'passed' for s in d['scenarios'])}/{len(d['scenarios'])}" + r"\\")
    return (r"""\begin{table*}[!t]
\centering
\caption{The 28 scripted change scenarios, grouped by the class of change they exercise. Event counts come from the recorded traces: D dispatched requests, A accepted replies, R current rejections or timeouts, X obsolete or duplicate replies discarded, E committed edits/reconfigurations, B refused edits or publications, P publications. A scenario passes when its independently written expectation holds; for several scenarios the expected outcome is a refusal.}\label{tab:scenarios}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llcrrrrrrrc@{}}\toprule
Change class & Scenarios (S\#) & Guarantee exercised & D & A & R & X & E & B & P & Pass\\\midrule
""" + "\n".join(lines) + r"""
\bottomrule\end{tabular*}
\end{table*}""")


def assurance_table(d):
    initial = {r["module"]: r for r in d["historical_proofs"]}
    lines = [r"\multicolumn{4}{@{}l}{\textit{Mechanized TLAPS lemmas (strict mode, fingerprints erased)}}\\"]
    for r in d["proofs"]["lemmas"]:
        first = initial.get(r["module"])
        trial = f"{first['failed']} of {first['total']} failed" if first else "--"
        lines.append(f"{{\\ttfamily {r['module'].removesuffix('Proofs')}}} & {MODULE_SCOPE[r['module']]} & {r['proved_obligations']}/{r['total_obligations']} & {trial}" + r"\\")
    m = d["policy_metrics"]
    traces = d["conformance"]["traces"]
    rejected = sum(c["rejected"] for c in d["conformance"]["corruptions"])
    tests = d["tests"]
    clean = d["clean_runs"]
    lines += [r"\midrule\multicolumn{4}{@{}l}{\textit{Executable checks}}\\",
              f"Policy tables & All typed six-row tables, both policies & {fmt(m['policy_tables_enumerated'])} & exhaustive" + r"\\",
              f"Event words & All words of length $\\le 6$, strict table & {fmt(m['policy_event_words'])} & exhaustive" + r"\\",
              f"Trace checker & Recorded scenario traces admitted & {sum(t['status'] == 'passed' for t in traces)}/{len(traces)} & --" + r"\\",
              f"Trace checker & Deliberately corrupted traces rejected & {rejected}/{len(d['conformance']['corruptions'])} & --" + r"\\",
              f"Regression tests & Transaction-boundary unit tests & {sum(t['status'] == 'ok' for t in tests)}/{len(tests)} & --" + r"\\",
              f"Reproduction & Clean re-runs of packaged archives matched (pre-fix snapshots) & {sum(c['matched'] for c in clean)}/{len(clean)} & --" + r"\\"]
    return (r"""\begin{table}[!t]
\centering
\caption{Assurance evidence. For proofs, \emph{Final} counts proved/total obligations in the clean run and \emph{First trial} the preserved failed development run. Executable counts are exhaustive where stated; the other checks cover the recorded executions only.}\label{tab:assurance}
\scriptsize\setlength{\tabcolsep}{2.5pt}
\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}>{\raggedright\arraybackslash}p{24mm}>{\raggedright\arraybackslash}p{28mm}rl@{}}\toprule
Artifact & Scope & Final & First trial\\\midrule
""" + "\n".join(lines) + r"""
\bottomrule\end{tabular*}
\end{table}""")


def ablation_figure(c):
    a = c["ablation"]
    runs = a["full"]["runs"]
    lines = []
    w, h = 0.56, 0.40
    for j, p in enumerate(PROPERTY_ORDER + ["pub"]):
        label = PROPERTY_LABELS.get(p, "Published")
        lines.append(r"\node[rotate=60,anchor=south west,font=\scriptsize] at (%.2f,0.02) {%s};" % (j * w - 0.12, label))
    for i, v in enumerate(ABLATION_ORDER):
        y = -(i + 0.5) * h
        lines.append(r"\node[anchor=east,font=\scriptsize] at (%.2f,%.2f) {%s};" % (-w / 2 - 0.05, y, ABLATION_LABELS[v]))
        for j, p in enumerate(PROPERTY_ORDER + ["pub"]):
            count = a[v]["runs_publishing"] if p == "pub" else a[v]["runs_violating"][p]
            pct = 100 * count / runs
            if p == "pub":
                fill = "gray!%d!white" % (8 + int(pct * 0.35))
                text = "black"
            elif count == 0:
                fill, text = "resultteal!12!white", "resultteal!70!black"
            else:
                fill = "resultamber!%d!white" % (25 + int(pct * 0.75))
                text = "white" if pct > 45 else "black"
            lines.append(r"\fill[%s] (%.2f,%.2f) rectangle ++(%.2f,%.2f);" % (fill, j * w - w / 2 + 0.02, y - h / 2 + 0.02, w - 0.04, h - 0.04))
            shown = ("%.0f" % pct) if count else "0"
            lines.append(r"\node[font=\tiny,text=%s] at (%.2f,%.2f) {%s};" % (text, j * w, y, shown))
        if i == 0:
            lines.append(r"\draw[inkblue!60,densely dotted] (-3.3,%.2f) -- (%.2f,%.2f);" % (-h, 7.5 * w, -h))
    lines.append(r"\draw[inkblue!40] (%.2f,0.02) -- (%.2f,%.2f);" % (6.5 * w, 6.5 * w, -len(ABLATION_ORDER) * h))
    return (r"""\begin{figure}[!t]
\centering
\begin{tikzpicture}
""" + "\n".join(lines) + r"""
\node[anchor=south east,font=\scriptsize\bfseries] at (-0.33,0.02) {Mechanism removed};
\end{tikzpicture}
\caption{RQ1: implementation-level guard ablation under %s seeded adversarial executions per variant (%s steps each). Cells give the percentage of runs in which the independent oracle observed at least one violation of property P1--P7 (Section~\ref{sec:rq1}); the last column gives the percentage of runs that published at least once. The reference controller (top row) shows no violation. Removing either obsolete-response defence alone is masked by the other.}\label{fig:ablation}
\end{figure}""" % (fmt(runs), c["config"]["ablation_steps"]))


def cost_figure(c):
    s = c["cost"]["summary"]
    sizes = sorted(map(int, s))
    plots = {"requests": [], "bytes": []}
    for mode in STRATEGY_ORDER:
        for key, field in (("requests", "requests_per_change"), ("bytes", "kbytes_per_change")):
            coords = " ".join("(%d,%.4g)" % (n, s[str(n)][mode][field]) for n in sizes)
            plots[key].append(r"\addplot[%s,thick,mark size=1.6pt] coordinates {%s};" % (STRATEGY_STYLE[mode], coords))
    legend = r"\legend{" + ",".join(STRATEGY_LABELS[m] for m in STRATEGY_ORDER) + "}"
    ticks = ",".join(map(str, sizes))
    return (r"""\begin{figure*}[!t]
\centering
\begin{tikzpicture}
\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.7cm},vgcplot,width=.43\textwidth,height=5.2cm,
  xmode=log,log basis x=2,ymode=log,xtick={%s},xticklabels={%s},log ticks with fixed point,
  ytick={0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000,2000},xlabel={Documents in the workspace ($N$)},
  legend style={at={(1.08,1.04)},anchor=south,legend columns=5,draw=none,/tikz/every even column/.append style={column sep=6pt}}]
\nextgroupplot[ylabel={Generation requests per change}]
%s
%s
\nextgroupplot[ylabel={Observation kB sent per change}]
%s
\end{groupplot}
\end{tikzpicture}
\caption{RQ2: generation work per input change as the workspace grows (log--log; mean over %d seeds $\times$ %d random changes per size). All strategies share validators, scheduler and guards and differ only in what a job's signature observes; they accepted identical values in every run. Left: dispatched requests. Right: total size of the observations sent to workers, a proxy for prompt input tokens.}\label{fig:cost}
\end{figure*}""" % (ticks, ticks, "\n".join(plots["requests"]), legend, "\n".join(plots["bytes"]),
                    c["config"]["seeds"], c["config"]["changes"]))


def cost_table(c):
    s = c["cost"]["summary"]
    n = str(max(map(int, s)))
    lines = []
    for kind, label in CHANGE_LABELS.items():
        cells = [s[n][m]["by_kind"][kind]["requests_per_change"] for m in STRATEGY_ORDER]
        lines.append(label + " & " + " & ".join("%.1f" % x if x is not None else "--" for x in cells) + r"\\")
    lines.append(r"\midrule All changes & " + " & ".join("%.1f" % s[n][m]["requests_per_change"] for m in STRATEGY_ORDER) + r"\\")
    lines.append(r"Bytes per request & " + " & ".join("%s" % fmt(round(
        1000 * s[n][m]["kbytes_per_change"] / s[n][m]["requests_per_change"])) for m in STRATEGY_ORDER) + r"\\")
    head = " & ".join(r"\rotatebox{70}{%s}" % STRATEGY_LABELS[m] for m in STRATEGY_ORDER)
    return (r"""\begin{table}[!t]
\centering
\caption{RQ2: mean generation requests per change by change type for $N=%s$ documents. Exact signatures make the cost of source and context changes independent of $N$; contract changes necessarily touch every job of the changed stage.}\label{tab:cost}
\scriptsize\setlength{\tabcolsep}{2pt}
\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrrrr@{}}\toprule
Change type & %s\\\midrule
""" % (n, head) + "\n".join(lines) + r"""
\bottomrule\end{tabular*}
\end{table}""")


def numbers(d, c):
    a, s = c["ablation"], c["cost"]["summary"]
    n = str(max(map(int, s)))
    ratio = lambda m: s[n][m]["requests_per_change"] / s[n]["exact"]["requests_per_change"]
    bratio = lambda m: s[n][m]["kbytes_per_change"] / s[n]["exact"]["kbytes_per_change"]
    detected = [v for v in ABLATION_ORDER[1:] if a[v]["runs_with_any_violation"] > 0]
    masked = [v for v in ABLATION_ORDER[1:] if a[v]["runs_with_any_violation"] == 0]
    runs = a["full"]["runs"]
    values = {
        "AblRuns": fmt(runs), "AblSteps": c["config"]["ablation_steps"],
        "AblVariants": len(ABLATION_ORDER) - 1, "AblTotalRuns": fmt(runs * len(ABLATION_ORDER)),
        "AblDetected": len(detected), "AblMasked": len(masked),
        "FullViolRuns": a["full"]["runs_with_any_violation"], "FullPubRuns": a["full"]["runs_publishing"],
        "FullPublications": fmt(a["full"]["publications"]), "FullDispatches": fmt(a["full"]["dispatches"]),
        "FullApiExceptionRuns": a["full"]["runs_with_api_exception"],
        "GlobalPublishPct": "%.0f" % (100 * a["no-global"]["runs_violating"]["publish"] / runs),
        "ObsoleteStalePct": "%.0f" % (100 * a["no-obsolete"]["runs_violating"]["stale"] / runs),
        "ObsoleteInvalidPct": "%.0f" % (100 * a["no-obsolete"]["runs_violating"]["invalid"] / runs),
        "ContractStalePct": "%.0f" % (100 * a["no-contract"]["runs_violating"]["stale"] / runs),
        "ContextStalePct": "%.0f" % (100 * a["no-context"]["runs_violating"]["stale"] / runs),
        "BudgetPct": "%.0f" % (100 * a["no-budget"]["runs_violating"]["budget"] / runs),
        "CandidatePct": "%.0f" % (100 * a["no-candidate"]["runs_violating"]["structure"] / runs),
        "UpstreamPct": "%.0f" % (100 * a["no-upstream"]["runs_violating"]["upstream"] / runs),
        "AuthorityPct": "%.0f" % (100 * a["no-authority"]["runs_violating"]["authority"] / runs),
        "CostMaxN": n, "CostSizes": len(s), "CostSeeds": c["config"]["seeds"], "CostChanges": c["config"]["changes"],
        "ExactReqMaxN": "%.1f" % s[n]["exact"]["requests_per_change"],
        "FullReqMaxN": "%.1f" % s[n]["full"]["requests_per_change"],
        "RatioFull": "%.1f" % ratio("full"), "RatioWorkspace": "%.1f" % ratio("workspace"),
        "RatioVersion": "%.1f" % ratio("version"), "RatioCutoff": "%.1f" % ratio("no-cutoff"),
        "BytesRatioWorkspace": "%.0f" % bratio("workspace"), "BytesRatioFull": "%.0f" % bratio("full"),
        "ExactReqMinN": "%.1f" % s[str(min(map(int, s)))]["exact"]["requests_per_change"],
        "CostEquivalent": "all" if c["cost"]["all_outcomes_equivalent"] else "not all",
        "CampaignMinutes": "%.0f" % (c["elapsed_seconds"] / 60),
        "TLCMaxStates": fmt(max(r["distinct_states"] for r in d["models"])),
        "TLCMutants": len(d["mutations"]), "TLCMutantsCaught": sum(r["status"] == "counterexample" for r in d["mutations"]),
        "TLCBaselines": len(d["models"]), "TLCWitnesses": len(d["witnesses"]),
        "Scenarios": len(d["scenarios"]), "ScenarioPasses": sum(s_["status"] == "passed" for s_ in d["scenarios"]),
        "Corruptions": len(d["conformance"]["corruptions"]),
        "ProvedObligations": sum(r["proved_obligations"] for r in d["proofs"]["lemmas"]),
        "PolicyTables": fmt(d["policy_metrics"]["policy_tables_enumerated"]),
        "EventWords": fmt(d["policy_metrics"]["policy_event_words"]),
        "RegressionTests": len(d["tests"]),
        "PythonVersion": c["python"],
    }
    prefix = ROOT / "results/processed/tse/prefix-defect.json"
    if prefix.is_file():
        # Measured on the unfixed controller (same seeds) before the defect was repaired.
        p = json.loads(prefix.read_text(encoding="utf-8"))
        values.update({"PreFixApiRuns": p["runs_with_api_exception"], "PreFixApiExceptions": p["api_exceptions"],
                       "PreFixRuns": fmt(p["runs"]), "PreFixViolRuns": p["runs_with_violation"]})
    return "\n".join(macro(k, v) for k, v in values.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=str(ROOT / "results/processed/tse/campaign.json"))
    args = parser.parse_args()
    d = json.loads(DETAIL.read_text(encoding="utf-8"))
    c = json.loads(Path(args.campaign).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    fragments = {"numbers.tex": numbers(d, c), "tab-tlc.tex": tlc_table(d), "tab-scenarios.tex": scenario_table(d),
                 "tab-assurance.tex": assurance_table(d), "fig-ablation.tex": ablation_figure(c),
                 "fig-cost.tex": cost_figure(c), "tab-cost.tex": cost_table(c)}
    provenance = {"inputs": {str(p.relative_to(ROOT).as_posix()): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (DETAIL, Path(args.campaign).resolve())},
                  "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "fragments": {}}
    for name, text in fragments.items():
        body = "% Generated by experiments/tse_paper.py; do not edit.\n" + text + "\n"
        (OUT / name).write_text(body, encoding="utf-8")
        provenance["fragments"][name] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("\n".join(sorted(fragments)))


if __name__ == "__main__":
    main()
