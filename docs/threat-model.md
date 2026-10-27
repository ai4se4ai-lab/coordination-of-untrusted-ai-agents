# Scope of adversarial behavior

Scripted workers may return malformed/invalid values, duplicate or delay a reply,
or time out. Source/context/configuration can change while a request is pending.
Workers cannot mutate Python controller internals or invoke authoritative edits.
Trusted host callers control ingress and configuration; authorization of external
users is outside this artifact. Generated code remains data.

No guarantee covers crash recovery, malicious validators, corrupted storage,
hostile threads bypassing public APIs, independent worker side effects,
confidentiality, cryptographic authenticity or arbitrary cyclic workflows.
