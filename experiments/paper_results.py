"""Auditable descriptive figures/tables from recorded experiments, no inference."""
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from scripts.common import ROOT, write_json


MODEL_NAMES = {"one-k1": "One job, k=1", "one-k2": "One job, k=2", "chain-k1": "Chain, k=1",
 "chain-k2-frozen": "Chain, frozen", "fanout-frozen": "Fan-out, frozen", "workflow-frozen": "Workflow, frozen",
 "one-reversion": "Reversion", "parallel-delivery": "Parallel delivery", "chain-terminal": "Chain, temporal"}
FAULT_NAMES = {"no-cancel": "Cancellation omitted", "no-recheck": "Recheck omitted", "obsolete-both": "Both defenses omitted",
 "budget-reset": "Exhausted budget reset", "publish-suspended": "Suspension ignored", "revoked-authority": "Authority ignored",
 "stale-publication": "Revision check omitted", "contract-omitted": "Contract omitted", "membership-omitted": "Selected context omitted"}
TARGETS = {"CurrentCommit": "Current observation", "BudgetSafety": "Episode accounting", "SuspensionPublication": "No suspended stage",
 "AuthorityCommit": "Current authority", "RevisionPublication": "Checked revision", "ContractCommit": "Contract identity", "ContextCommit": "Context identity"}
WITNESS_NAMES = {"reach-acceptance": "Acceptance", "reach-exhaustion": "Exhaustion", "reach-suspension": "Suspension",
                 "reach-publication": "Publication (empty)", "reach-contractchange": "Contract change"}
TEST_NAMES = {"boolean_not_integer_and_malformed_rows_rejected": "Primitive types and malformed rows",
 "deletion_recreation_does_not_reauthorize_old_request": "Deletion/recreation request identity",
 "duplicate_after_accept_cannot_overwrite": "Duplicate cannot overwrite acceptance",
 "durable_counter_not_claimed": "Unchanged-episode budget retention",
 "forged_publication_check_cannot_install": "Forged publication token rejection",
 "kernel_namespace_encoding_and_missing_reference": "Namespace injectivity / missing reference",
 "proposal_and_input_aliases_do_not_modify_accepted_state": "Mutable proposal alias isolation",
 "publication_is_total_at_each_partial_repair_boundary": "Publication on partial repair states",
 "rejected_reconfiguration_rolls_back_everything": "Atomic reconfiguration rollback",
 "required_views_and_structural_reads_cannot_be_omitted": "Mandatory views and structural reads",
 "unavailable_context_blocks_publication_and_reactivates": "Context suspension / reactivation",
 "zero_match_workflow_can_publish": "Successful zero-match completion"}
CHANNELS = ["D", "A", "R", "X", "E", "P", "B", "O"]


def tex(text):
    return str(text).replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


def derive(reports, sources, summary):
    inputs = {}

    def read(path):
        path = Path(path)
        inputs[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text(encoding="utf-8")

    def raw(kind, filename):
        return ROOT / "results/raw" / sources[kind]["run"] / filename

    model_manifest = json.loads(read(raw("models", "manifest.json")))
    bounds = {m["id"]: m for m in model_manifest["configuration"]["matrix"]}
    models = [{**r, "bounds": bounds[r["id"]], "ratio": r["generated_states"] / r["distinct_states"]}
              for r in reports["models"]]
    paths = {}
    for kind in ("mutations", "witnesses"):
        paths[kind] = []
        for row in reports[kind]:
            log = read(raw(kind, row["log"]))
            states = [int(n) for n in re.findall(r"^State (\d+):", log, re.M)]
            paths[kind].append({**row, "shortest_actions": max(states)-1 if states else None})
    scenarios = []
    traces = {}
    for row in reports["case-study"]:
        t = json.loads(read(raw("case-study", row["trace"])))
        traces[row["id"]] = t
        counts = Counter({k: 0 for k in CHANNELS})
        for e in t["events"]:
            action, outcome = e["action"], e["outcome"]
            channel = ("D" if action == "Dispatch" and outcome == "dispatched" else
                       "A" if action == "ResolveAccepted" else
                       "R" if action in ("ResolveRejected", "Timeout") else
                       "X" if action == "DiscardObsoleteOrDuplicate" else
                       "E" if action in ("EditSource", "UpdateContext", "Reconfigure") and outcome == "committed" else
                       "P" if action == "Publish" and outcome == "published" else
                       "O" if action == "OptionalObservationStep" else "B")
            counts[channel] += 1
        final = t["events"][-1]["after"] if t["events"] else t["initial"]
        dirty = sum(final["records"][j]["stamp"] != final["records"][j]["signature"] or
                    final["records"][j]["evidence_owner"] != json.loads(final["records"][j]["signature"])["owner"]
                    for j in final["active"])
        assert sum(counts.values()) == len(t["events"])
        assert counts["D"] == row["requests"]
        scenarios.append({**row, "channels": dict(counts), "events": len(t["events"]),
                          "final_dirty": dirty, "final_suspended": len(final["suspended"])})
    tests_log = read(raw("tests", reports["tests"]["log"]))
    tests = [{"test": name, "name": TEST_NAMES.get(name.removeprefix("test_"), name), "status": result}
             for name, result in re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. (\w+)$", tests_log, re.M)]
    historical_proofs = []
    history = Counter()
    for p in sorted((ROOT / "results/raw").glob("*/manifest.json")):
        manifest = json.loads(p.read_text())
        if manifest["kind"] not in {"models", "mutations", "witnesses", "proofs", "case-study", "conformance", "tests", "clean-reproduction", "baseline", "spec-check"}:
            continue
        read(p)
        history[manifest["kind"], manifest["status"]] += 1
        if manifest["kind"] == "proofs":
            report_path = p.parent / "results.json"
            if not report_path.exists():
                continue
            report = json.loads(read(report_path))
            if any(r["status"] == "failed" for r in report.get("lemmas", [])):
                for r in report["lemmas"]:
                    log = read(p.parent / r["log"])
                    failed = re.search(r"(\d+)/(\d+) obligations failed", log)
                    proved = re.search(r"All (\d+) obligations proved", log)
                    historical_proofs.append({"run": manifest["run_id"], "module": r["module"], "status": r["status"],
                       "total": int(failed[2]) if failed else int(proved[1]) if proved else None,
                       "failed": int(failed[1]) if failed else 0 if proved else None,
                       "elapsed_seconds": r["elapsed_seconds"]})
    cuts = []
    for sid, name, action, last in (("S02", "No change", None, False), ("S08", "Unselected context", "UpdateContext", False),
                                   ("S10", "Equal content/version", "UpdateContext", True),
                                   ("S16", "Equal API repair", "Reconfigure", False), ("S17", "Tightened clause", "EditSource", False)):
        events = traces[sid]["events"]
        indexes = [i for i, e in enumerate(events) if e["action"] == action] if action else [len(events)]
        cut = indexes[-1 if last else 0]
        before = sum(e["action"] == "Dispatch" and e["outcome"] == "dispatched" for e in events[:cut])
        after = sum(e["action"] == "Dispatch" and e["outcome"] == "dispatched" for e in events[cut:])
        cuts.append({"id": sid, "name": name, "cut_event_index": cut, "requests_before": before, "requests_after": after})
    clean_runs = []
    for p in sorted((ROOT / "results/raw").glob("*clean-reproduction*/results.json")):
        report = json.loads(read(p))
        clean_runs.append({"run": p.parent.name, "matched": report["scientific_outcomes_match"],
                           "checksums": report["checksums_verified"], "archive_sha256": report["archive_sha256"],
                           "stage_exit_codes": report["stage_exit_codes"]})
    return {"sources": sources, "inputs_sha256": inputs, "models": models, **paths, "scenarios": scenarios,
            "proofs": reports["proofs"], "historical_proofs": historical_proofs, "tests": tests,
            "conformance": reports["conformance"], "request_interventions": cuts, "clean_runs": clean_runs,
            "history": [{"kind": kind, "statuses": {status: history[kind, status] for status in ("passed", "failed", "inconclusive")},
                         "runs": sum(n for (k, _), n in history.items() if k == kind)} for kind in sorted({k for k, _ in history})],
            "policy_metrics": next(r["metrics"] for r in reports["case-study"] if r["id"] == "S28"),
            "summary": {k: v for k, v in summary.items() if k != "sources"}}


def table(caption, label, columns, header, rows, size=r"\small"):
    return "\n".join([r"\begin{table}[tbp]", r"\centering", r"\caption{"+caption+r"}\label{"+label+"}",
                      size, r"\setlength{\tabcolsep}{3pt}", r"\renewcommand{\arraystretch}{1.13}",
                      r"\begin{tabularx}{\linewidth}{@{}"+columns+r"@{}}\toprule", header+r"\\\midrule",
                      *rows, r"\bottomrule\end{tabularx}", r"\end{table}"])


def row(*cells):
    return " & ".join(map(str, cells)) + r"\\"


def model_table(d):
    return table("Detailed bounded TLC baseline results. $J$: jobs; $k$: attempt cap; $m$: environmental-change cap; "
                 "$S$: distinct states; $G$: generated states including duplicates. Seconds include JVM startup for one invocation.",
                 "tab:exploration", "Xrrrrrrr", "Configuration & $J$ & $k$ & $m$ & $S$ & $G$ & $G/S$ & s",
                 [row(MODEL_NAMES[r["id"]],r["bounds"]["jobs"],r["bounds"]["k"],r["bounds"]["max_changes"],
                      f'{r["distinct_states"]:,}',f'{r["generated_states"]:,}',f'{r["ratio"]:.2f}',f'{r["elapsed_seconds"]:.3f}') for r in d["models"]],r"\footnotesize")


def model_figure(d):
    labels = ",".join("{"+MODEL_NAMES[r["id"]]+"}" for r in d["models"])
    coords = lambda key: " ".join(f'({r[key]},{i})' for i,r in enumerate(d["models"]))
    return r"""\begin{figure}[tbp]
\centering
\begin{tikzpicture}
\begin{axis}[vgcplot,xbar,bar width=4pt,width=.82\linewidth,height=7.5cm,
 xmode=log,log basis x=10,xmin=1,xmax=10000,
 xlabel={States (logarithmic scale)},ylabel={},
 ytick={0,1,2,3,4,5,6,7,8},yticklabels={"""+labels+r"""},
 y dir=reverse,enlarge y limits=.09,
 legend style={at={(.5,1.04)},anchor=south,legend columns=2,draw=none}]
\addplot[fill=inkblue,draw=inkblue] coordinates {"""+coords("distinct_states")+r"""};
\addplot[fill=resultteal,draw=resultteal] coordinates {"""+coords("generated_states")+r"""};
\legend{Distinct states,Generated states}
\end{axis}
\end{tikzpicture}
\caption{State-space profiles for the nine baseline configurations. The log axis makes frozen and changing-input instances legible together. Generated states include repeated successors; the gap is not a count of independent tests or proof strength.}\label{fig:state-space}
\end{figure}"""


def path_figure(d):
    parts = [r"\begin{figure}[tbp]\centering", r"\begin{tikzpicture}",
             r"\begin{groupplot}[group style={group size=1 by 2,vertical sep=1.9cm},vgcplot,width=.76\linewidth,height=5.3cm,xmin=0,xmax=4,xtick={0,1,2,3,4},yticklabel style={xshift=-2pt},y dir=reverse,enlarge y limits=.16]"]
    for title, rows, color in [("Detected coordination faults", [r for r in d["mutations"] if r["shortest_actions"] is not None], "resultamber"),
                               ("Expected nonvacuity witnesses",d["witnesses"],"resultteal")]:
        names = [FAULT_NAMES[r["id"]] if r["id"] in FAULT_NAMES else WITNESS_NAMES[r["id"]] for r in rows]
        parts.append(r"\nextgroupplot[title={"+title+r"},xlabel={Actions in shortest recorded path},ytick={"+",".join(map(str,range(len(rows))))+"},yticklabels={"+",".join("{"+n+"}" for n in names)+"}]")
        for i,r in enumerate(rows):
            parts.append(r"\addplot["+color+r",line width=1.4pt,mark=*,mark options={fill="+color+r"}] coordinates {(0,"+str(i)+") ("+str(r["shortest_actions"])+","+str(i)+")};")
    parts += [r"\end{groupplot}\end{tikzpicture}",r"\caption{Shortest paths extracted from TLC counterexample logs, excluding the initial state. The upper panel records actual safety violations in deliberate mutants; the lower panel records desired reachable states by violating their negations. The two surviving single-defense mutants have no counterexample path and are excluded from the upper panel, not assigned length zero.}\label{fig:shortest-paths}",r"\end{figure}"]
    return "\n".join(parts)


def heatmap(d):
    maximum = max(r["channels"][k] for r in d["scenarios"] for k in CHANNELS)
    lines = [r"\begin{figure}[tbp]\centering",r"\begin{tikzpicture}[x=.53cm,y=.42cm,every node/.style={font=\footnotesize}]"]
    for panel in range(2):
        offset = panel*11
        lines.append(r"\node[anchor=west,font=\small\bfseries] at ("+str(offset-1)+r",2.0) {"+("S01--S14" if panel==0 else "S15--S28")+"};")
        for col,ch in enumerate(CHANNELS):
            lines.append(r"\node at ("+str(offset+col)+",1.05) {"+ch+"};")
        for rindex,r in enumerate(d["scenarios"][panel*14:panel*14+14]):
            lines.append(r"\node[anchor=east] at ("+str(offset-.6)+","+str(-rindex)+") {"+r["id"]+"};")
            for col,ch in enumerate(CHANNELS):
                value=r["channels"][ch]; shade=0 if value==0 else 15+int(80*value/maximum)
                lines.append(r"\filldraw[fill=resultteal!"+str(shade)+r"!white,draw=white] ("+str(offset+col-.47)+","+str(-rindex-.47)+") rectangle ++(.94,.94);")
                lines.append(r"\node[text="+("white" if shade>=65 else "inkblue")+"] at ("+str(offset+col)+","+str(-rindex)+") {"+str(value)+"};")
    lines.append(r"\node[anchor=east] at (4,-15) {Count};")
    for i,value in enumerate(sorted({0,maximum//4,maximum//2,3*maximum//4,maximum})):
        x=5+1.5*i;shade=0 if value==0 else 15+int(80*value/maximum)
        lines.append(r"\filldraw[fill=resultteal!"+str(shade)+r"!white,draw=inkblue!15] ("+str(x-.47)+",-15.47) rectangle ++(.94,.94);")
        lines.append(r"\node[text="+("white" if shade>=65 else "inkblue")+"] at ("+str(x)+",-15) {"+str(value)+"};")
    lines += [r"\end{tikzpicture}",r"\caption{Recorded event composition for every predefined scenario. Cells contain exact counts with one shared color key. D: dispatch; A: accepted response; R: current rejection/timeout; X: obsolete/duplicate discard; E: committed source/context/configuration edit; P: publication; B: refused guard or edit; O: optional observer stutter. Categories partition each trace. S28 checks the policy language outside controller transitions, so its zero row is intentional.}\label{fig:scenario-heatmap}",r"\end{figure}"]
    return "\n".join(lines)


def requests_figure(d):
    parts=[r"\begin{figure}[tbp]\centering",r"\begin{tikzpicture}",r"\begin{axis}[vgcplot,ybar,bar shift=0pt,bar width=16pt,width=.96\linewidth,height=6.4cm,ymin=0,ymax=5,ytick={0,1,2,3,4,5},xtick={0,1,2,3,4},xticklabels={S02,S08,S10,S16,S17},xlabel={Scenario intervention},ylabel={Requests after intervention},nodes near coords,point meta=y]"]
    for i,r in enumerate(d["request_interventions"]):
        parts.append(r"\addplot[fill="+("resultamber" if r["requests_after"] else "resultteal")+r",draw=none] coordinates {("+str(i)+","+str(r["requests_after"])+")};")
    parts += [r"\end{axis}\end{tikzpicture}",r"\caption{Requests recorded after selected intervention boundaries, excluding each scenario's setup. S02: unchanged repair pass; S08: unselected context update; S10: equal selected content at a new context version; S16: architecture contract change repaired to equal API content; S17: tightened source clause followed by repair. These are different deterministic interventions, not matched performance benchmarks or samples of language-model cost.}\label{fig:request-deltas}",r"\end{figure}"]
    return "\n".join(parts)


def render(d):
    parts=[r"\section{Experimental results and discussion}\label{sec:results}",
 r"\subsection{Evidence selection and interpretation}",
 r"The following descriptive analysis covers the final archived campaign of each experiment type, together with failed proof-development trials and clean-directory reproductions. Every plotted value is derived from immutable reports, trace records or shortest-path logs; the input hashes and derived cells are recorded in \texttt{results/processed/document-service-v1/detailed-results.json}. Repeated development runs remain in the archive inventory. They are reproducibility/debugging records, not independent samples. No confidence interval, significance test, generative success probability or measured speedup is inferred from these deterministic fixtures and exhaustive finite enumerations.",
 r"\subsection{State-space structure and model-checking effort}",model_figure(d)]
    m={r["id"]:r for r in d["models"]}
    parts.append(f"Figure~\\ref{{fig:state-space}} and Table~\\ref{{tab:exploration}} expose the effect of the declared bounds. Raising the one-job attempt cap from one to two increases distinct states from {m['one-k1']['distinct_states']} to {m['one-k2']['distinct_states']} ({m['one-k2']['distinct_states']/m['one-k1']['distinct_states']:.2f} times), while permitting two environmental changes in the reversion instance reaches {m['one-reversion']['distinct_states']:,} distinct states. These are separate configurations, not asymptotic scaling estimates. The frozen four-stage workflow has only {m['workflow-frozen']['distinct_states']} distinct states: strict prerequisites serialize eligibility and the environment cannot edit it. A small count here reflects restricted behavior, not stronger verification or superior runtime performance.")
    parts.append(r"The $G/S$ ratio in Table~\ref{tab:exploration} describes repeated generated successors relative to distinct states. It is not a cache-hit rate of the Python controller. The recorded wall times are single local invocations with JVM startup, fixed one-worker execution and a 768 MB heap. Startup and host activity can dominate such small models; these durations document completed runs within their time limits and are not a controlled throughput comparison. The temporal configuration uses explicit aggregate fairness and frozen inputs; its passing result remains a finite liveness check.")
    parts += [r"\FloatBarrier",r"\subsection{Proof obligations, failed trials and remaining scope}"]
    parts.append(table("Scoped TLAPS outcomes for the final clean run. Counts are generated obligations, including supporting obligations; these are not counts of full controller theorems.","tab:proof-results","Xrrrrl","Module & Total & Proved & Omitted & s & Status",
      [row(tex(r["module"]),r["total_obligations"],r["proved_obligations"],r["omitted_obligations"],f'{r["elapsed_seconds"]:.3f}',r["status"].capitalize()) for r in d["proofs"]["lemmas"]],r"\footnotesize"))
    parts.append(table("Recorded initial proof-development trial. A failed obligation is preserved as a failed proof attempt, not a reachable-state counterexample. Later explicit type/construction-assumption references repaired these scoped proofs.","tab:proof-development","Xrrrl","Module & Total & Failed & s & Status",
      [row(tex(r["module"]),r["total"],r["failed"],f'{r["elapsed_seconds"]:.3f}',r["status"].capitalize()) for r in d["historical_proofs"]],r"\footnotesize"))
    parts.append(r"Table~\ref{tab:proof-results} separates the successful scoped modules from the unfinished central proof gate. The isolated counter lemma does not count arbitrary controller histories; the admission lemma derives its conclusion from the explicit commit guard, not from an induction over all actions. Kernel results rely on injective constructors and current reference domains, while policy results concern the restricted extensional relation. Table~\ref{tab:proof-development} retains the earlier failures, including missing explicit assumption references. The increase in generated obligations after repair reflects proof elaboration and cited assumptions, not additional independently verified software features. Internal review also exposed insufficient history-shape constraints in a proposed induction invariant; strengthening those constraints excludes that review witness but does not establish the full invariant's inductiveness.")
    parts += [r"\FloatBarrier",r"\subsection{Mutation sensitivity and nonvacuity}",path_figure(d)]
    parts.append(table("Complete mutant campaign. CEX: intended property violated; survive: exhaustive pass under the remaining defense. Path length excludes the initial state; -- means no counterexample was found. $S$: distinct states; $G$: generated states. All use one job, k=1 and at most one environmental change.","tab:mutation-detail","Xlrrrrl","Fault & Target & Path & $S$ & $G$ & s & Result",
      [row(FAULT_NAMES[r["id"]],TARGETS.get(r.get("violated"),"Safety invariant"),r["shortest_actions"] if r["shortest_actions"] is not None else "--",r["distinct_states"],r["generated_states"],f'{r["elapsed_seconds"]:.3f}',"CEX" if r["status"]=="counterexample" else "Survive") for r in d["mutations"]],r"\scriptsize"))
    parts.append(table("Nonvacuity campaign: shortest desired-state witnesses. Each expected counterexample violates the negation of a reachability target and therefore indicates coverage, not an error in the baseline protocol.","tab:witness-detail","Xrrrr","Reachability target & Actions & Distinct & Generated & s",
      [row(WITNESS_NAMES[r["id"]],r["shortest_actions"],r["distinct_states"],r["generated_states"],f'{r["elapsed_seconds"]:.3f}') for r in d["witnesses"]],r"\footnotesize"))
    parts.append(r"Figure~\ref{fig:shortest-paths} makes the short failure mechanisms visible: obsolete commitment, counter reset and changed contract/context require only a few actions in these abstractions. The two surviving mutants remove one obsolete-response defense at a time. Their survival is expected redundancy under the other defense, not evidence that the omitted guard is unnecessary in a larger runtime. A mutation is counted as detected only when its named intended property fails. Exploration stops at the first shortest counterexample, so mutant state counts cannot be compared to exhaustive baseline state counts as a measure of scalability. Table~\ref{tab:witness-detail} independently demonstrates reachable acceptance, exhaustion, suspension, publication and contract change; a safety invariant could otherwise pass in a model that never admits useful work.")
    parts.append(r"The shortest publication witness first deletes the only job and then publishes the permitted zero-match workflow. It therefore establishes reachability of publication but does not itself demonstrate publication after nonempty generated work. S01, S20 and S26 supply recorded implementation executions with successful nonempty publication; a separate shortest formal witness requiring a nonempty accepted workflow has not been collected here. Keeping this distinction visible prevents a reachable empty completion from being mistaken for coverage of every successful workflow.")
    parts += [r"\FloatBarrier",r"\subsection{Scenario-level workload and terminal outcomes}",heatmap(d)]
    parts.append(r"Table~\ref{tab:scenario-results} reports every scenario separately. Counts include setup and are cumulative within each trace; a passing scenario means that its independent expectation held, including expected rejection, blockage or conflict. It does not mean publication succeeded. $Q$ counts suspended required jobs in this restricted per-document implementation; dirty active jobs are listed separately. Publication occurs only where the scenario explicitly invokes it successfully. Several fixtures share an execution but assert different consequences: S14/S15 exercise the same exhaustion path, S03/S17 use the tightened-clause path, and S07/S09 use the selected-context addition. They must not be interpreted as independent statistical replications.")
    parts += [r"{\footnotesize\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.14}",
      r"\begin{longtable}{@{}lp{3.0cm}rrrrrrrr@{}}",
      r"\caption{All scripted scenarios. D: dispatches; A: accepted responses; R: current rejection/timeout; X: discarded replies; P: publications; U: dirty active jobs at the end; Q: suspended required jobs at the end. Milliseconds are single recorded scenario invocations including setup. All expectations passed.}\label{tab:scenario-results}\\",
      r"\toprule ID & Scenario & D & A & R & X & P & U & Q & ms\\\midrule\endfirsthead",
      r"\multicolumn{10}{l}{\textit{Table \thetable\ continued}}\\\toprule ID & Scenario & D & A & R & X & P & U & Q & ms\\\midrule\endhead",
      r"\midrule\multicolumn{10}{r}{\textit{Continued on next page}}\\\endfoot\bottomrule\endlastfoot"]
    for r in d["scenarios"]:
        c=r["channels"]
        parts.append(row(r["id"],tex(r["name"]),c["D"],c["A"],c["R"],c["X"],c["P"],r["final_dirty"],r["final_suspended"],f'{1000*r["elapsed_seconds"]:.1f}'))
    parts += [r"\end{longtable}}",requests_figure(d)]
    parts.append(table("Request counts around selected interventions. The cut index is the zero-based event position before the intervention; S02 cuts after its completed setup because its unchanged repair pass emits no new event. Values are read from recorded dispatch events.","tab:request-interventions","lXrrr","ID & Intervention & Cut & Before & After",
                       [row(r["id"],r["name"],r["cut_event_index"],r["requests_before"],r["requests_after"]) for r in d["request_interventions"]],r"\footnotesize"))
    parts.append(r"Figure~\ref{fig:request-deltas} removes setup from a small set of interpretable change traces (Table~\ref{tab:request-interventions}). No relevant change, unselected context and a new version with equal selected content cause no additional request. Equal architecture output after a contract change requires the architecture's own new proposal but lets compatible descendants reuse evidence. Tightening the source clause reaches different implementation/verification observations despite an unchanged API, so the repair propagates. This is observed suppression of unnecessary calls in these fixtures. There is no full-regeneration baseline or provider token measurement, and these unequal interventions cannot establish a general speedup or cost-saving percentage.")
    metrics=d["policy_metrics"]
    parts.append(table("Finite-language and recorded-execution checks. Domain sizes describe this restricted language; no sampling uncertainty is attached to exhaustive finite counts.","tab:validation-domains","Xrl","Check & Count & Interpretation",
       [row("Typed policy tables, both settings",f'{metrics["policy_tables_enumerated"]:,}',"Exhaustive enumeration"),
        row("Strict-policy event words, length 0--6",f'{metrics["policy_event_words"]:,}',"All bounded words"),
        row("Malformed table fixtures",metrics["malformed_cases"],"Specific negative examples"),
        row("Controller traces admitted",sum(r["status"]=="passed" for r in d["conformance"]["traces"]),"Recorded executions only"),
        row("Corrupted traces rejected",sum(r["rejected"] for r in d["conformance"]["corruptions"]),"Checker sensitivity"),
        row("Transaction regression tests",len(d["tests"]),"Executed tests, not proof")],r"\footnotesize"))
    parts.append(r"S28 has no controller transition events in Figure~\ref{fig:scenario-heatmap}: its work is exhaustive validation of the finite proposal language and bounded interpretation of event words. Its conforming empty controller trace does not supply evidence about the interpreter. That evidence instead comes from the dedicated oracle assertions summarized in Table~\ref{tab:validation-domains}, together with the separate mathematical argument and scoped policy lemmas. The bounded event-word campaign does not replace an unbounded interpreter refinement proof, and the malformed fixtures do not enumerate arbitrary malformed syntax.")
    parts += [r"\FloatBarrier",r"\subsection{Regression coverage, trace-checker sensitivity and reproduction}"]
    parts.append(table("Individual transaction regressions and deliberately corrupted traces. OK denotes the expected outcome, including rejection of every corrupted trace; it is not a universal correctness verdict.","tab:negative-controls","lXl","Family & Check & Outcome",
      [r"\multicolumn{3}{l}{\textit{Transaction regression tests}}\\"]+
      [row(f'T{i+1:02d}',r["name"],r["status"].upper()) for i,r in enumerate(d["tests"])]+
      [r"\midrule\multicolumn{3}{l}{\textit{Trace corruption controls}}\\"]+
      [row(f'C{i+1:02d}',tex(r["fault"].replace("-"," ")),"Rejected" if r["rejected"] else "Missed") for i,r in enumerate(d["conformance"]["corruptions"])],r"\footnotesize"))
    parts.append(r"The controls in Table~\ref{tab:negative-controls} target different boundaries: API transactions, structural admissibility, mutable aliases and replayed semantic events. In particular, acceptance events containing hidden source/context/contract changes must be rejected even when the proposed value itself is valid. These controls test sensitivity of the checker and the exercised implementation paths; they neither authenticate the log nor exclude omitted final suffixes or untested behaviors. A uniform pass column therefore records satisfaction of predefined expectations, not a confidence estimate for deployed reliability.")
    parts.append(table("Inventory of archived domain-verification campaigns before this manuscript expansion. Pass/fail/inconclusive refer to whole-stage status. Inconclusive proof stages include successful scoped lemmas but an open central gate. Paper-build and tool-doctor invocations are excluded from experiment counts.","tab:campaign-history","Xrrrr","Campaign & Runs & Pass & Fail & Inconclusive",
      [row(tex(r["kind"]),r["runs"],r["statuses"]["passed"],r["statuses"]["failed"],r["statuses"]["inconclusive"]) for r in d["history"]],r"\footnotesize"))
    parts.append(table("Clean extracted-directory reproductions of two packaged snapshots (ZIP SHA-256 prefixes identify them). A match compares the reported scientific outcomes; the incomplete baseline and proof stages are expected nonzero exits. Existing host tools and the pinned proof-container image are reused, so this is not a fresh-OS experiment.","tab:clean-reproductions","llrrl","Run & ZIP hash prefix & Files & Open stages & Outcomes",
      [row(f'R{i+1}',r'\texttt{'+r["archive_sha256"][:10]+'}',r["checksums"],sum(v!=0 for v in r["stage_exit_codes"].values()),"Matched" if r["matched"] else "Mismatch") for i,r in enumerate(d["clean_runs"])],r"\footnotesize"))
    parts.append(r"Tables~\ref{tab:campaign-history} and~\ref{tab:clean-reproductions} prevent a polished final pass from erasing development failures or open obligations. The first proof trial's failed modules are retained explicitly in Table~\ref{tab:proof-development}; its whole-stage classification is inconclusive because the central proof gate remains unfinished. Historical baseline reproduction is also inconclusive because the cited original explorers were absent. The clean ZIP reproductions recover the same finite counts and scenario outcomes with those nonzero statuses intact. Repetition demonstrates procedural reproducibility on the recorded host environment; it supplies no independent samples for a significance test. The evidence supports guard debugging, scoped proof steps and conformance of recorded executions, while full parameterized safety, history-budget induction and action correspondence remain open.")
    parts += [r"\FloatBarrier"]
    # Keep discussions with floats; only flush at the section boundary.
    return "\n\n".join([p for p in parts[:-1] if p != r"\FloatBarrier"] + [parts[-1]])


def update_paper(paper, detail):
    source = paper.read_text(encoding="utf-8")
    start,end="% BEGIN GENERATED TLC RESULTS","% END GENERATED TLC RESULTS"
    prefix,tail=source.split(start,1);_,suffix=tail.split(end,1)
    source=prefix+start+"\n"+model_table(detail)+"\n"+end+suffix
    start,end="% BEGIN GENERATED DETAILED RESULTS","% END GENERATED DETAILED RESULTS"
    if start not in source:
        anchor=r"\section{Related work and formal-method choices}"
        source=source.replace(anchor,start+"\n"+end+"\n\n"+anchor)
    prefix,tail=source.split(start,1);_,suffix=tail.split(end,1)
    source=prefix+start+"\n"+render(detail)+"\n"+end+suffix
    paper.write_text(source,encoding="utf-8")
