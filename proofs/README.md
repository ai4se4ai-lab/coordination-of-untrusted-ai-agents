# Proof status and obligations

No proof is counted as checked until a clean `tlapm` run succeeds and its log,
backend/version, dependency hashes and obligation count are captured.
Budget.tla contains three checked isolated-counter lemmas, not a completed controller
budget proof. The scoped modules have clean successful TLAPS logs; see proof-status.json for the latest run and counts. The full Init/Next invariant, history counting, action simulation,
reconfiguration, kernel interface and policy trace induction remain open.

`python scripts/reproduce.py proofs` returns nonzero on an unavailable prover or
an unproved central obligation. Finite TLC results cannot satisfy this gate.
Use a glibc Linux environment with TLAPS; Docker Desktop's musl service distro
is not a development Linux installation. No WSL distribution is installed by this
artifact and no privileged system change is performed.
