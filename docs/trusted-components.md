# Trusted components

Scientific proof trust: TLAPS parser/obligation generator, SMT translation and
bundled Z3 4.8.9. The current runs do not request Isabelle replay of SMT results.
Kernel injectivity and reference-domain/type conditions are explicit assumptions,
not inferred for arbitrary transformation programs. Finite TLC additionally
trusts its evaluator, state storage and fingerprints (collision probability is
reported in raw logs); exploration is not an unbounded proof.

Reference execution trust: Python interpreter/stdlib, host process, immutable-copy
serialization, RLock, observation builder, rank checker, normalizer, validators,
publication check and policy interpreter. No worker network/file/deploy effects
are granted. Trace events are trusted as records of execution; the checker can
reject inconsistent or omitted interior events but cannot detect an omitted final
suffix without an external end marker. It does not establish log authenticity. Deterministic edit/acceptance reconciliation is independently reconstructed; agreement still leaves common specification/implementation mistakes possible.
