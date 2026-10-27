# Verified generative coordination

Replication package for the paper

> M. Babaei, **"Safe Coordination of Untrusted AI Agents,"**
> manuscript submitted to *IEEE Transactions on
> Software Engineering*. Source: [docs/paper-tse/main.tex](docs/paper-tse/main.tex).

## What this project is

Multi-agent LLM frameworks split software development among agents that write
requirements, designs, code and tests. Each answer can look valid while the
workflow as a whole still goes wrong: a slow agent answers a question that has
since changed, two valid outputs disagree on an interface, or a reviewer added
late is skipped. These are coordination failures, and better prompting does not
remove them.

This project defines a coordination semantics in which agents only **propose**
primitive values. A deterministic controller owns artifact structure, dependency
tracking and publication. Every generated attribute carries an **exact dependency
signature** covering its source footprint, the shared context selected for it and
its generation contract. A guarded transition system:

- accepts a proposal only if it answers the *current* question;
- invalidates exactly the work a change affects;
- bounds generation attempts per dependency episode;
- publishes only globally consistent snapshots.

The repository contains three versions of these ideas:

1. **TLA+ specifications** of the protocol, with scoped TLAPS proofs and bounded
   TLC model checks ([specification/](specification/), [proofs/](proofs/), [models/](models/)).
2. **A Python reference controller** with no dependencies outside the standard
   library ([src/vgc/](src/vgc/)).
3. **An evaluation** that drives the controller through a document-service case
   study and randomized adversarial campaigns ([case-study/](case-study/), [experiments/](experiments/)).

**No language model is called anywhere.** Proposals come from scripted or
adversarial providers ([src/vgc/providers/scripted.py](src/vgc/providers/scripted.py)),
so every number in the paper is a deterministic function of recorded seeds and
fixtures. You don't need API keys, credentials or network access, apart from the
one-time tool download.

### Scope of the claims

This is a research artifact. It is not a verified production system. The scoped
TLAPS lemmas pass, but the central parameterized safety/budget invariant and the
refinement mapping from asynchronous to atomic execution are **proved only on
paper**. The `proofs` stage therefore exits nonzero on purpose (see
[Expected outcomes](#expected-outcomes)). The [claim–evidence matrix](docs/claim-evidence-matrix.csv)
lists each theorem with its level of evidence (paper proof, machine-checked,
finite-checked or tested) and the work that remains. [docs/deviations.md](docs/deviations.md)
records where the artifact departs from the original development plan.

## Repository layout

| Path | Contents |
|---|---|
| [specification/](specification/) | TLA+ modules: `Core`, `AsyncController`, `AtomicController`, `StructuralKernel`, `DocumentPolicy`, `CaseStudy` |
| [proofs/](proofs/) | TLAPS proof modules and [proof-status.json](proofs/proof-status.json) (latest obligation counts) |
| [models/](models/) | TLC configurations: `smoke/`, `core/` (13 safety, reachability and liveness configs), `mutants/` (9 seeded protocol bugs) |
| [src/vgc/](src/vgc/) | Reference controller: observations, scheduler, structure kernel, validators, scripted providers |
| [case-study/document-service/](case-study/document-service/) | Five-stage ranked workflow, requirements, policies, fixtures and the 28 pre-registered scenarios (`scenarios/campaign.json`) |
| [verification/](verification/) | Independent trace-conformance oracle; `baseline/` holds the original user-supplied sources |
| [experiments/](experiments/) | Campaign protocol, analysis, RQ1/RQ2 campaign (`tse_campaign.py`), TSE fragment generator (`tse_paper.py`) |
| [tests/](tests/) | Regression tests (`unittest`) |
| [scripts/](scripts/) | `reproduce.py` (single entry point), tool bootstrap, packaging, clean-room verification |
| [environment/](environment/) | Pinned toolchain lock file (URLs and SHA-256) and the TLAPS proof container |
| [results/raw/](results/raw/) | One directory per run: manifest, exact command, source hashes, source snapshot, logs |
| [results/processed/](results/processed/) | Aggregated data that the paper is generated from |
| [docs/paper-tse/](docs/paper-tse/) | **TSE manuscript** (IEEEtran). Every evaluation number and plot is `\input` from `generated/` |
| [docs/paper-emse/](docs/paper-emse/) | Earlier Springer version of the manuscript (kept for reference) |
| [docs/](docs/) | Semantics, assumptions, threat model, trusted components, toolchain provenance, reproducibility notes |

## Requirements

| Tool | Needed for | Tested version |
|---|---|---|
| Python ≥ 3.11 (standard library only) | everything | 3.13.14 |
| Java ≥ 11 | TLC (`spec-check`, `models`, `mutations`, `witnesses`) | Amazon Corretto 11.0.16.1 |
| Docker Desktop/Engine **or** native Linux TLAPS | `proofs` | Docker 29.5.3; TLAPS 1.6.0-pre (Z3 4.8.9) |
| pdfLaTeX + BibTeX | building the manuscripts | MiKTeX 24.1 / TeX Live |

The scripts were developed on Windows 11 and run in CI on Ubuntu 24.04
([.github/workflows/](.github/workflows/)). If `java` is not on `PATH`, point
`VGC_JAVA` at the executable. TLC runs with one worker and a 768 MB heap, so an
ordinary laptop is enough.

Tool binaries are **not** in the repository. `bootstrap_tools.py` downloads
`tla2tools.jar` and the TLAPS archive into `.tools/` and checks every byte against
[environment/toolchain.lock.json](environment/toolchain.lock.json). If an upstream
asset has changed, it refuses to continue. [docs/toolchain.md](docs/toolchain.md)
gives the provenance of each tool.

## Quick start (about 5 minutes, Python only)

```text
git clone <this repository> && cd verified-generative-coordination
python scripts/reproduce.py tests          # 13 regression tests
python scripts/reproduce.py case-study     # 28 scenarios, records traces
python scripts/reproduce.py conformance    # independent oracle replays those traces
python experiments/tse_campaign.py --quick # small RQ1/RQ2 smoke run
```

Each command prints the run directory it created and `passed` or `failed`.

## Reproducing the paper's results

Every `reproduce.py` stage writes `results/raw/<UTC timestamp>-<stage>-<id>/`
containing `manifest.json` (command, commit, git status, OS, Python, SHA-256 of
every source file), `sources.zip` (a snapshot of those sources), `results.json`
and the raw tool logs. Committed runs from the paper are already in
[results/raw/](results/raw/), so you can compare against them.

### 1. Set up tools

```text
python scripts/bootstrap_tools.py
docker build -f environment/Dockerfile.proofs -t vgc-tlaps:local .   # proofs only
python scripts/reproduce.py doctor          # reports which tools were found
```

The proof container pins its Debian base image by digest and pins package
versions. TLAPS needs glibc ≥ 2.38. Docker Desktop's internal distribution
cannot run it directly, which is why the container is provided.

### 2. Run the stages

| Research question / paper element | Command | Approx. time |
|---|---|---|
| Specs parse (SANY) | `python scripts/reproduce.py spec-check` | < 1 min |
| RQ1/RQ4: bounded model checking (Table "TLC") | `python scripts/reproduce.py models --profile core` | ~1 min |
| RQ1: seeded mutants are caught | `python scripts/reproduce.py mutations` | ~1 min |
| RQ1: reachability witnesses | `python scripts/reproduce.py witnesses` | ~1 min |
| RQ4: scoped TLAPS lemmas | `python scripts/reproduce.py proofs --timeout 90` | ~1 min |
| RQ4: regression tests | `python scripts/reproduce.py tests` | < 1 min |
| RQ3: scenario campaign (Table "Scenarios") | `python scripts/reproduce.py case-study` | < 1 min |
| RQ3/RQ4: independent trace conformance | `python scripts/reproduce.py conformance` | < 1 min |
| Aggregate the latest campaign of each stage | `python scripts/reproduce.py analyze` | < 1 min |
| **RQ1 guard ablation + RQ2 invalidation cost** (Figs. ablation/cost, Table cost) | `python scripts/reproduce.py tse-campaign` | **15–30 min** |
| Regenerate the TSE tables, figures and numbers | `python scripts/reproduce.py tse-paper` | seconds |

Then build the manuscript:

```text
cd docs/paper-tse
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

`python scripts/reproduce.py all --profile core` runs every formal and scenario
stage in sequence (doctor → baseline → spec-check → proofs → models → mutations →
witnesses → tests → case-study → conformance → analyze → claims → paper →
package) and prints a JSON summary of exit codes. It does **not** include the
TSE campaign, so run `tse-campaign` and `tse-paper` separately afterwards.

### 3. How the numbers reach the paper

No evaluation number is typed into the TSE manuscript by hand:

| Fragment in [docs/paper-tse/generated/](docs/paper-tse/generated/) | Generated from |
|---|---|
| `tab-tlc.tex`, `tab-scenarios.tex`, `tab-assurance.tex` | `results/processed/document-service-v1/detailed-results.json` (written by `analyze`) |
| `fig-ablation.tex`, `fig-cost.tex`, `tab-cost.tex` | `results/processed/tse/campaign.json` (written by `tse-campaign`) |
| `numbers.tex` (all `\Macro{}` values in the text) | both of the above, plus `results/processed/tse/prefix-defect.json` |

[generated/provenance.json](docs/paper-tse/generated/provenance.json) records the
SHA-256 of every input, of the generator and of every fragment. `analyze` always
selects the **most recent** run of each stage and keeps failed cases in the
denominator. Older runs remain in `results/raw/` but are not mixed in. If you
change a source file, rerun the affected stages before `analyze`.

### Expected outcomes

These are the headline values in [numbers.tex](docs/paper-tse/generated/numbers.tex):

| Quantity | Paper value |
|---|---|
| RQ1: randomized runs (300 seeds × 11 controller variants, 120 steps each) | 3,300 |
| RQ1: safety violations in the reference controller | 0 |
| RQ1: ablations that violate their targeted property | 8 of 10 (the 2 single obsolete-reply defenses are individually redundant) |
| RQ1: TLC mutants caught / baseline configs with no violation | 7 of 9 / 9 |
| RQ2: requests per change at N = 32, exact vs. full regeneration | 10.8 vs. 128.0 (11.9×) |
| RQ2: reduction vs. whole-workspace / version-keyed / no-cutoff strategies | 8.1× / 3.0× / 2.3× |
| RQ2: accepted values identical across strategies | all runs |
| RQ3: scenarios passed | 28 of 28 |
| RQ4: TLAPS obligations proved (scoped lemmas) | 25 |
| RQ4: regression tests | 13 |

**What should match exactly:** all counts, verdicts and ratios. The campaigns are
deterministic given the seeds, and TLC state counts are fixed for the same
sources and configuration.
**What will differ:** wall-clock timings, TLC fingerprint randomization and PDF
bytes.

**Nonzero exit codes that are expected:**

- `proofs` exits nonzero even when every scoped lemma passes, because the central
  obligations are still open. Finite TLC results never satisfy this gate.
- `baseline` reports `inconclusive` because some of the original historical
  materials were never supplied.
- `all` therefore exits nonzero. Read its JSON summary: every other stage should
  report `0`.

## Clean-room reproduction

To check that the artifact works outside this checkout:

```text
python scripts/reproduce.py package   # writes dist/vgc-artifact-0.1.0.zip + checksums
python scripts/verify_package.py      # extracts to a fresh directory, downloads pinned
                                      # tools, reruns the pipeline, compares outcomes
```

`verify_package.py` writes `dist/clean-reproduction.json`, which includes the hash
of the archive it tested, and leaves the fresh directory in place for inspection.
The archive contains no `.git`, credentials, virtual environments, tool binaries
or TLC state databases. See [docs/reproducibility.md](docs/reproducibility.md) for
details.

## Further documentation

- [docs/semantics.md](docs/semantics.md): the coordination semantics
- [docs/assumptions.md](docs/assumptions.md) and [docs/threat-model.md](docs/threat-model.md):
  what is assumed about agents, the environment and the attacker
- [docs/trusted-components.md](docs/trusted-components.md): the trusted computing base
- [specification/README.md](specification/README.md) and [proofs/README.md](proofs/README.md):
  what the TLA+ model and the proofs cover and what they don't
- [case-study/document-service/README.md](case-study/document-service/README.md):
  the case-study workflow
- [experiments/README.md](experiments/README.md): campaign protocol and the
  statistical interpretation of results (deterministic fixtures, not samples)

## Citation

If you use this artifact, please cite the paper above. Machine-readable metadata
is in [CITATION.cff](CITATION.cff). An archival DOI will be added on acceptance.

## License

Code and documentation: MIT ([LICENSE](LICENSE)). The Springer class and style
files in `docs/paper-emse/` are included unchanged and remain under the
publisher's terms.
