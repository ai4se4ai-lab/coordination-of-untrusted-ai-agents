# Document lifecycle coordination contracts (independent fixture v1)

This is a newly specified coordination case study with scripted proposals. It is
not a deployed HTTP server or a copy of an existing implementation or dataset.

* R01: Every source document has a stable string identity. A source entry has
  exactly one Boolean `strict` policy field. Engine targets have a separate
  injectively encoded namespace. Architecture declares create/read/update/archive/
  list and a locally well-typed identifier choice. Allocation of downstream policy
  artifacts additionally requires string identity; an integer choice causes
  candidate normalization to reject the entire update.
* R02: The implementation attribute is an inert six-row JSON decision table on
  `{open,archived} x {read,put,archive}`. Archive returns 200 and enters archived;
  read returns 200 and preserves state; put preserves state and returns 409 iff
  strict and archived, otherwise 200. A fixed interpreter performs exactly the
  indicated state/status transition. All rows must exist exactly once.
* R03: The verification view records coverage for R01--R03 and its identifier
  type. Publication requires all required views usable and no suspended stages
  or active requests, plus agreement of architecture/verification identifier
  types. Adding security review requires assessment coverage for all five
  interface operations, one job per document.

The operations list is interface metadata: no create/list persistence or payload
behavior is proved by the six-row language. Verification/review coverage fields
are checked metadata, not proof that a worker executed independent security tests.
Roles are producer capabilities, not a modeled end-user authentication system.
Confidentiality, storage durability and payload integrity are outside R01--R03.

Revision v2 changes strict=false to strict=true without changing the API. This
must invalidate implementation and verification observations. An unrelated
document or nonmatching context finding must preserve unaffected observations.
