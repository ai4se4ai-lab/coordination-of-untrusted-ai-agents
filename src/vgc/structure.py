"""Restricted finite single-target allocate/resolve kernel."""
from dataclasses import asdict
from .types import Binding


def check_bindings(bindings):
    if any(not isinstance(b, Binding) for b in bindings):
        raise ValueError("expected Binding records")
    if any(not isinstance(b.stage, str) or not isinstance(b.owner, str) or not b.owner or
           not isinstance(b.contract, str) or type(b.rank) is not int or b.rank < 0 or
           not isinstance(b.prerequisites, tuple) or any(not isinstance(p, str) for p in b.prerequisites)
           for b in bindings):
        raise ValueError("invalid binding schema")
    by_stage = {b.stage: b for b in bindings}
    if len(by_stage) != len(bindings):
        raise ValueError("duplicate producer")
    for b in bindings:
        if any(p not in by_stage or by_stage[p].rank >= b.rank
               for p in b.prerequisites):
            raise ValueError("unranked or missing prerequisite")
    return by_stage


def allocate_resolve(keys, references):
    # Exact tuple encoding, not ambiguous string concatenation.
    import json
    targets = {key: "target:" + json.dumps(key, separators=(",", ":")) for key in keys}
    if len(set(targets.values())) != len(targets):
        raise ValueError("identity collision")
    resolved = {}
    for key in keys:
        refs = references.get(key, ())
        if any(ref not in targets for ref in refs):
            raise ValueError("dangling reference")
        resolved[targets[key]] = tuple(targets[ref] for ref in refs)
    return targets, resolved
