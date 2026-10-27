"""One-time evidence-oriented revision; numerical regions are populated by analysis."""
from common import ROOT


def main():
    path = ROOT / "docs/paper/main.tex"
    source = path.read_text(encoding="utf-8")
    start = source.index(r"\section{Executable finite-instance validation}")
    end = source.index(r"\section{Related work", start)
    replacement = r"""\section{Formal artifact and executable validation}\label{sec:checking}
The artifact separates four forms of evidence: mathematical arguments in this paper, scoped TLAPS lemmas, bounded TLC exploration, and recorded executions of a Python reference controller. None substitutes for the others. In particular, the full parameterized inductive invariant and the asynchronous-to-atomic action correspondence have not been discharged in TLAPS. The reference implementation has no general refinement proof.

\subsection{Formalization and proof status}
\texttt{specification/Core.tla} and \texttt{AsyncController.tla} formalize ranked prerequisites, exact observations, historical acceptance, episode counts, request history, suspension, contract/authority changes, and publication evidence. The finite value relation is deliberately abstract: a proposed value is valid when it equals the observed source value. It is not an execution of the case-study table validator. Structural matching, failed candidate normalization and cross-view joint constraints are not fully connected to this protocol formalization; they are exercised separately in the implementation scenarios.

\texttt{AtomicController.tla} gives independent Attempt, Accept, Fail, Edit and Publish actions. A complete abstraction map must erase transport history and evidence detail while preserving attempts, episodes, accepted values and publication revision. Supplying that checked map remains an open obligation for Theorem~\ref{thm:refinement}; finite agreement cannot establish it.

The scoped proof modules are \texttt{Budget} (initial, increment and stuttering bounds for an isolated counter), \texttt{ControllerSafety} (the admission guard implies current authorized valid commitment), \texttt{StructuralKernelProofs} (coverage, unique producers and reference range under explicit construction hypotheses), and \texttt{DocumentPolicyProofs} (extensional validator equivalence, archive absorption and the archived-put conflict). These results support individual proof steps. They do not establish preservation of the whole controller invariant, history counting across changing episodes, or the concrete Python interpreter's correctness. The central proof gate is explicitly incomplete in \texttt{proofs/proof-status.json}.

TLAPS build \texttt{5f5037f} runs with its bundled Z3 4.8.9 in a pinned Linux container. Clean proof runs use strict mode and erase fingerprints. The trusted path includes the proof manager, translation and SMT backend; these runs do not replay SMT results in Isabelle. The first proof-development run failed obligations that lacked explicit references to construction/type assumptions. Those failures and the revised runs are preserved separately; no assumption equal to the advertised safety conclusion was introduced.

\subsection{Finite protocol exploration}
The TLC matrix is predefined in \texttt{models/matrix.yaml}. Each configuration fixes the job set, ranked parent relation, two abstract source/context values, attempt cap and environmental-change bound. One worker and a 768 MB Java heap are used with an explicit per-run timeout. The generated-state count includes repeated successors; it is not a transition or execution-trace count. Terminal self-loops are explicit and deadlock detection stays enabled. Exact commands, limits, tool versions, source hashes, status and raw output are retained for each run.

% BEGIN GENERATED TLC RESULTS
% Populated from immutable raw reports by experiments/analysis.py.
% END GENERATED TLC RESULTS

The frozen-input temporal configuration checks eventual terminal classification, which may include exhausted jobs and suspended descendants. It assumes weak fairness of aggregate dispatch and request settlement, and permits no further environmental changes. It is a finite-instance liveness check, not a mechanized proof of Theorem~\ref{thm:termination} for arbitrary workflows. The two-change configuration exercises lifecycle and observation reversion; the independent-job configuration allows reordered delivery.

Mutation runs are separate from baseline correctness runs. Removing both cancellation and commit-time rechecking admits dispatch, edit, obsolete commitment. Resetting an exhausted counter violates the history-counting invariant. Omitting contract or selected-context identity permits commitment under changed inputs. Other mutations admit suspended publication, revoked authority or an old checked revision. Removing either obsolete-response defense alone survives because the other remains. Identity-reuse and tentative-write model mutants remain outstanding; their corresponding reference-controller regressions do not replace that missing model evidence.

The original manuscript referred to two earlier Python explorers and historical state counts. Their sources and reports were absent from the supplied checkout, so those counts are not reproduced or presented as current evidence. New TLC results use different models and must not be compared numerically to those earlier counts.

\section{An executable document-service case study}\label{sec:case-study}
The newly specified study uses four ranked views per source document: requirements, architecture, implementation and verification. A fifth security-review view can be added during execution. Each view has one stable target and one generated JSON attribute per document. A requirements proposal lists stable clauses R01--R03 and the current Boolean archive policy. An architecture proposal declares create/read/update/archive/list and an identifier type. The implementation proposal is the restricted table of Section~\ref{sec:discharged}; verification records clause coverage and an identifier type. Security review records required operation-assessment coverage. These coverage fields are checked metadata, not evidence that an independent security analysis or executable test suite was performed.

R01 requires stable string document identities and valid target/reference construction. Architecture locally permits a typed string or integer choice, but downstream structural expressions require strings; this gives a concrete locally valid proposal whose whole transaction must be rejected. R02 specifies the exact finite lifecycle state/status relation. R03 requires complete view metadata and matching architecture/verification identifier types before publication. The declared create/list operations are interface metadata; their storage and payload behavior are not implemented or verified by the six-row table. End-user authentication, confidentiality and persistent storage remain outside the study.

\begin{table}[tb]
\caption{Ranked case-study binding contracts}\label{tab:bindings}
\small\begin{tabularx}{\linewidth}{@{}lXX@{}}\toprule
View & Declared inputs & Local check\\\midrule
Requirements & Source policy & Clause IDs, exact Boolean policy\\
Architecture & Usable requirements & Operation list, typed ID choice\\
Implementation & Interface, source clause, selected findings & Exact six-row policy table\\
Verification & Table, source clause, selected findings & Coverage and typed ID metadata\\
Security (added) & Verification, selected findings & Operation-assessment coverage\\\bottomrule
\end{tabularx}
\end{table}

The controller serializes public actions with one in-process lock. It copies a candidate, installs the proposed primitive value privately, and recomputes complete downstream structure before installing any effect. Request identities and counters survive all changes within one controller lifetime, but are not durable across restart. Source/context ingress is a trusted-host capability; workers receive no direct edit authority. Proposal providers are deterministic scripts, with no model credentials or remote calls.

Observations store exact canonical JSON, including the owner, contract, source clause, usable predecessor values and full selected finding membership. Audit-only context versions are excluded from worker inputs. Historical accepted records can be reused after reactivation only under equal observation, compatible owner/contract and current permission. Regranting the same owner under an unchanged contract permits such reuse; policies forbidding it must change contract identity. These choices instantiate A0--A4 within the documented in-process trust boundary. A5--A6 govern scheduling; A7 is discharged only for the exact finite policy relation, with weaker metadata guarantees for the other validators.

Figure~\ref{fig:case-trace} shows a representative pending-request edit. A source reversion does not restore authority to the canceled request, even when the observation bytes return to their earlier value. A separate scenario changes the architecture contract, repairs it to equal output, and restores compatible descendants from cache without another downstream request.
\begin{figure}[tb]
\centering
\begin{tikzpicture}[node distance=5mm, every node/.style={font=\small}]
\node[box,text width=92mm] (a) {Dispatch request $(j,e,1)$ on observation $o_0$};
\node[box,text width=92mm,below=of a] (b) {Edit clause: reconcile to $o_1$, cancel request, suspend descendants};
\node[box,text width=92mm,below=of b] (c) {Old response arrives: discard; historical identity grants no write};
\node[box,text width=92mm,below=of c] (d) {Repair under a fresh episode; publish only the current checked revision};
\draw[arr] (a)--(b); \draw[arr] (b)--(c); \draw[arr] (c)--(d);
\end{tikzpicture}
\caption{A scripted change trace through atomic controller actions. The final publication is conditional on all local and joint obligations}\label{fig:case-trace}
\end{figure}

Scenario inputs and independent expectations are fixed in \texttt{case-study/document-service/scenarios/campaign.json}. They cover unchanged/unselected content, selector additions, pending edits, source reversion, timeout/duplicate delivery, exhaustion, suspension/cache restoration, joint conflict, failed candidate rollback, reviewer changes, authority/contract changes, same-version context writers, stale global checks, observer loss and malformed ingress. The finite-language campaign separately exhausts typed tables and bounded event words; malformed table cases include absent/duplicate rows and incorrect primitive types.

% BEGIN GENERATED CAMPAIGN SUMMARY
% Populated by experiments/analysis.py.
% END GENERATED CAMPAIGN SUMMARY

The trace checker is implemented separately from controller admission code and independently evaluates finite contracts. It checks state continuity, ranked availability, exact observations, dispatch identity/counters, historical provenance, current authority, rejection rollback and publication snapshots. Its edit-normalization mapping is partial and its recorded events are trusted; it cannot detect a silently omitted final trace suffix without an external completion marker. Thus these are conformance results for recorded executions, not a general implementation-refinement theorem. Deterministic scenarios are neither independent statistical samples nor measurements of language-model quality or speed.

Reproduction commands, raw manifests, failed proof attempts and generated table-cell provenance are supplied locally. \texttt{python scripts/reproduce.py all --profile core} runs each stage and deliberately returns failure while baseline evidence or central proof obligations remain incomplete. A successful scenario or scoped lemma run cannot hide those open gates.

"""
    source = source[:start] + replacement + source[end:]
    source = source.replace("A reproducible finite-state exploration checks a small asynchronous instance and detects deliberately weakened guards.", "Scoped proof-assistant lemmas, bounded state exploration, and a scripted document-service case study exercise the obligations; full controller mechanization and implementation refinement remain open.")
    source = source.replace("We use a forward simulation at the coordination level and explicitly leave implementation refinement open.", "We give a mathematical forward simulation at the coordination level; its full mechanization and implementation refinement remain open.")
    source = source.replace("This is a theoretical study with an illustrative workflow and a finite-state validation artifact. No empirical performance or functional-correctness measurements are claimed. The accompanying explorers and their run reports are supplied locally with this manuscript; no public archive identifier has been assigned.", "This study supplies mathematical semantics, scoped proof artifacts, bounded model checks and scripted reference-controller scenarios. No real-model performance or unrestricted generated-code correctness measurements are claimed. Sources, raw reports, independent expectations and reproduction commands are supplied locally; no public archive identifier has been assigned. The full parameterized controller and refinement proof gates remain incomplete.")
    source = source.replace("The finite explorer does not establish scalability.", "The bounded model checks do not establish scalability.")
    path.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
