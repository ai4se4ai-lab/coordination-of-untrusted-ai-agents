# Verified generative coordination

A research artifact for coordinating untrusted proposals through exact dependency
observations, ranked transformations, bounded request episodes and atomic
publication. The reference controller uses scripted proposals and no paid API.

**Status: partial implementation of the development plan.** The full parameterized
controller safety/budget proof and asynchronous-to-atomic action correspondence
remain open. Scoped TLAPS lemmas, bounded TLC checks and passing recorded scenarios
must not be read as a verified production implementation.

The authoritative paper is [docs/paper/main.tex](docs/paper/main.tex), with a separate
bibliography. Original user sources are preserved in verification/baseline/.
The [progress report](docs/progress.md), [deviations](docs/deviations.md) and
[claim ledger](docs/claim-evidence-matrix.csv) distinguish completed and open work.

From Python 3.11+ (tested with 3.13.14):

```text
python scripts/bootstrap_tools.py
python scripts/reproduce.py doctor
python scripts/reproduce.py spec-check
python scripts/reproduce.py models --profile core
python scripts/reproduce.py mutations
python scripts/reproduce.py tests
python scripts/reproduce.py case-study
python scripts/reproduce.py conformance
python scripts/reproduce.py analyze
python scripts/reproduce.py claims
python scripts/reproduce.py paper
python scripts/reproduce.py package
python scripts/verify_package.py
```

Java 11+ is needed for TLC. Set `VGC_JAVA` if it is not on PATH. Local tool downloads
are verified against environment/toolchain.lock.json and excluded from bundles.
LaTeX/BibTeX and the normal TeX packages are needed for the paper. Publisher
class/style dependencies are included unchanged with recorded provenance.

For the scoped TLAPS run, use native Linux TLAPS or Docker Desktop/Engine:

```text
docker build -f environment/Dockerfile.proofs -t vgc-tlaps:local .
python scripts/reproduce.py proofs --timeout 90
```

The proof command returns nonzero while central obligations remain open, even when
the scoped lemmas pass. `all --profile core` executes independent stages and
propagates this incomplete status; absent historical baseline sources also return
inconclusive. No credentials, external model, deployment or publication is required.

Each run writes raw logs, exact commands, source hashes and a manifest under
results/raw/. Analysis selects the most recent campaign of each type, retains
failures in its denominator, and generates the paper's marked numerical regions.
See [reproducibility](docs/reproducibility.md) for clean-directory instructions.

The existing MIT LICENSE is preserved. The Springer files retain publisher terms.
No public archive DOI, artifact URL or submission claim is assigned here.
