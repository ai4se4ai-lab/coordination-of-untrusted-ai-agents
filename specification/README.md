# TLA+ scope

Core and AsyncController are a parameterized coordination protocol with ranked
parents, exact observations, historical records, dynamically suspended jobs,
nonreused episode/request identities, counted attempts, and publication evidence.
`EditField` is the abstract environment boundary. Each edit consumes MaxChanges;
this is a finite exploration bound, not an assumption for an unbounded safety proof.
Successful terminals have explicit stutters; deadlock detection remains enabled.

Validator outcomes use `v = observation.source`: a deliberately finite semantic
abstraction, **not** execution or verification of the Python case-study validator.
Structural matching, global joint constraints and candidate normalization failure
are not encoded in this protocol model. StructuralKernel and DocumentPolicy are
separate constant modules; their connection to Core remains an open obligation.
Python S18/S19 cover those boundaries only in recorded executions.

AtomicController specifies Attempt, Accept, Fail, Edit and Publish independently.
It omits transport history/evidence. A complete abstraction map must erase those
fields as well as pending requests and show compatibility of Reconcile. This
obligation is open; no checked implementation refinement is claimed.

No fairness/liveness claim is obtained from Safety. Infinite observation stutters
and environment activity are permitted. A frozen two-job configuration checks eventual terminal classification under explicit aggregate dispatch/settlement fairness. This does not establish the general progress theorem.
