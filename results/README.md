# Evidence storage

raw/<run-id>/ contains manifests, command output, result summaries and case traces.
Runs are never overwritten. Processed summaries reference selected raw runs by
hash. Baseline artifacts have their own provenance under verification/baseline/.
Model/proof timeouts, missing tools and failed obligations are not successes.

All fixtures are newly specified local data. There are no real provider outputs
or credentials. TLC state databases and TLAPS caches are excluded. Compact full
counterexample text is retained in mutation logs.
