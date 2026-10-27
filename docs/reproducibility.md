# Clean reproduction

Extract dist/vgc-artifact-0.1.0.zip into a new directory. Check
ARTIFACT-CHECKSUMS.json before running. The ZIP deliberately contains no .git,
credentials, virtual environments, tool binaries or TLC databases. Git metadata
will be reported as unavailable outside a checkout.

Install/use Python 3.11+ and Java 11+. Core Python commands require only stdlib.
Run bootstrap_tools.py; every downloaded byte is SHA-256 checked. Upstream rolling
pre-release assets are accepted only if they match the recorded hash; a changed
upstream asset fails explicitly. On Linux with native TLAPS, ensure its standard
library and backend tools are on PATH; otherwise build the pinned proof container.
The Dockerfile pins base digest and required Debian package versions. A complete
offline mirror of upstream binaries/deb packages is not included.

Use the command sequence in README.md. The `proofs` and `baseline` stages return
nonzero for open obligations/missing original materials. This is expected partial
artifact status, not a passing verification gate. `all` finishes independent stages
and returns nonzero if any required stage is incomplete or fails. Per-run model and
proof time limits can be changed with --timeout; TLC heap is fixed at 768 MB and
uses one worker. No Python RAM quota is enforced. Completed finite counts should
match for the same sources/configuration; timings and randomized TLC fingerprints
need not. PDF byte identity is not claimed.

Raw logs preserve failed proof-development runs as well as final campaigns. The
analysis default selects latest campaigns and records exact report hashes; it
does not discard failed cases within a selected campaign. Older runs remain
available. Do not mix raw reports from changed sources into a new summary.

The independent checker validates recorded guard/effect obligations only. It independently reconstructs deterministic reconciliation and cannot prove authenticity/completeness of
logs. Full implementation refinement and crash recovery are outside this release.

Run `python scripts/verify_package.py` after packaging to verify internal checksums, extract outside the checkout, download pinned tools, execute the full documented pipeline and compare scientific outcomes. It writes raw logs and dist/clean-reproduction.json with the tested archive hash. The fresh directory is retained for inspection. Expected incomplete proof/baseline statuses are checked explicitly.
