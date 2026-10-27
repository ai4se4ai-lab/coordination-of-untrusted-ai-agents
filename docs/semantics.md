# Semantic alignment and action interface

The authoritative mathematical semantics is docs/paper/main.tex. Core.tla is a
ranked protocol abstraction; its structural/validator interface connection remains
unproved. See specification/README.md for exact omissions.

The reference state contains immutable source/context snapshots with a context
CAS version, ranked binding contracts/owners, active targets and references,
historical records, active/suspended sets, pending requests, dispatch history,
nonce allocator, semantic revision and a published revision/snapshot.

| Action | Guard | Atomic effect |
|---|---|---|
| EditSource | source schema and trusted ingress; candidate normalizes | replace source, reconcile, cancel obsolete requests, advance revision |
| UpdateContext | valid immutable data and expected version matches | increment context version; reconcile selected content; advance revision |
| Dispatch | active dirty available job, no pending request, remaining budget | increment attempt; immutable request in pending and history |
| ResolveAccepted | active identity/episode, current exact observation, current owner grant, local type/validator pass, candidate normalizes | install entire candidate and evidence; remove request; advance revision |
| ResolveRejected/Timeout | current active request | remove it; charge work already counted; mark failed at k |
| Discard | obsolete, canceled or duplicate identity | no value write |
| Reconfigure | finite ranked unique producers and candidate normalization | replace configuration, reconcile authority/contracts, cancel affected requests, advance revision |
| Publish | Q empty, every active job usable, no pending request, joint check on identical current snapshot | install immutable snapshot/revision |
| OptionalObservationStep | none | authoritative stutter |

Usability is observation-stamp equality plus currently compatible owner; generated
prerequisites determine availability in increasing rank. It does not call the
validator: historical successful evidence and equal observations justify reuse.
Canonical JSON includes type, collection membership, selected content, source
clause where read, predecessor values, owner and full contract identity. No digest
is used for admission. Unobserved context versions are audit-only. Unavailability
is distinct from empty selection and removes dependent active targets/jobs.

Every changed signature or reactivation starts a fresh globally allocated episode.
Unchanged active reconciliation preserves attempts/failure. Requests use
(job,episode,attempt); late replies remain unauthorized after reversion/recreation.
Cache retention after authority changes follows decisions/003-implementation-scope.md.

The document-service configuration retains the four mandatory core views and declares every structural read in its ranked prerequisite ancestry; security review is optional.

The abstract machine retains counters and maps Dispatch to Attempt. Acceptance
maps to an atomic accepted update, rejection/timeout to Fail, delivery/observer
detail to stutters. A checked full forward simulation is still required. No
existing successful finite check establishes this projection universally.
