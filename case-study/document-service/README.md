# Independently specified ranked workflow

| Rank | View/owner | Reads | Local contract | Target |
|---|---|---|---|---|
| 0 | requirements-worker | document strict flag | R01--R03 IDs and exact Boolean flag | one requirements attribute/document |
| 1 | architecture-worker | usable requirements | operation set and typed ID choice | one interface attribute/document |
| 2 | implementation-worker | interface, source clause, matching context | exact total finite policy table | one table attribute/document |
| 3 | verification-worker | usable table, clause, matching context | coverage and typed ID field | one coverage attribute/document |
| 4 | security-worker (optional) | usable verification, matching context | assessment coverage metadata | one review attribute/document |

Every row includes the complete contract string and owner in its observation.
Selection re-evaluates the full matching set, including additions and absence.
The implementation prerequisite is unavailable until architecture is current.
Active traces reference earlier active targets; suspended descendants have no
active targets. Historical records remain private. Reactivation allocates a new
episode but compatible accepted evidence can suppress generation.

requirements.md and scenarios/campaign.json define expected behavior separately
from the controller. `src/vgc/validators.py` implements the concrete decoder and
validators. `verification/trace_conformance.py` implements a separate oracle.
Only the restricted policy language has an extensional correctness relation;
the other view validators check metadata/types. No real LLM is invoked.

Run `python scripts/reproduce.py case-study` and then `... conformance`.
