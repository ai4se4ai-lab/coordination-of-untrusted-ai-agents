"""Predeclared deterministic scenarios. Assertions are independent expectations."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from vgc.controller import Controller
from vgc.types import Binding
from vgc.scheduler import repair
from vgc.providers.scripted import valid_proposal
from vgc.validators import validate_table, interpret, table


def run_scenario(scenario_id):
    c = Controller()
    root = c.key("requirements", "d1")
    policy = c.key("implementation", "d1")
    architecture = c.key("architecture", "d1")
    verification = c.key("verification", "d1")
    if scenario_id in {"S01", "S02", "S03", "S04", "S06", "S07", "S08", "S09", "S10",
                       "S16", "S17", "S18", "S19", "S20", "S21", "S23", "S25", "S26"}:
        assert repair(c)
    if scenario_id == "S01":
        assert len(c.active) == 4 and len(c.targets) == 4
        assert all(c._usable(k) for k in c.active)
        assert c.publish() == "published"
    elif scenario_id == "S02":
        count = len(c.history)
        assert repair(c)
        assert len(c.history) == count
    elif scenario_id in {"S03", "S17"}:
        old = c.records[policy].stamp
        assert c.edit_source({"d1": {"strict": True}}) == "committed"
        assert not c._usable(policy) and policy in c.suspended
        assert repair(c)
        assert c.records[policy].stamp != old
        assert c.records[architecture].value["id_type"] == "string"
    elif scenario_id == "S04":
        c.edit_source({"d1": {"strict": False}, "d2": {"strict": False}})
        repair(c)
        old = {k: deepcopy(r) for k, r in c.records.items() if c.split(k)[1] == "d1"}
        c.edit_source({"d1": {"strict": False}, "d2": {"strict": True}})
        assert all(c.records[k] == r and c._usable(k) for k, r in old.items())
    elif scenario_id == "S05":
        assert c.edit_source({"d1": {"strict": False}, "d2": {"strict": False}}) == "committed"
        assert c.key("requirements", "d2") in c.active and len(c.targets) == 2
    elif scenario_id == "S06":
        assert c.edit_source({}) == "committed"
        assert not c.active and not c.targets and not c.references and not c.pending
    elif scenario_id in {"S07", "S09"}:
        old = c.records[policy].signature
        assert c.update_context(0, {"f1": {"document": "d1", "finding": "path policy"}}) == "committed"
        assert c.records[policy].signature != old and not c._usable(policy)
    elif scenario_id == "S08":
        before = {k: deepcopy(r) for k, r in c.records.items()}
        c.update_context(0, {"f2": {"document": "d2", "finding": "unselected"}})
        assert c.records == before
    elif scenario_id == "S10":
        c.update_context(0, {"f1": {"document": "d1", "finding": "same"}})
        repair(c)
        before = deepcopy(c.records)
        c.update_context(1, deepcopy(c.context))
        assert c.context_version == 2 and c.records == before
    elif scenario_id in {"S11", "S12"}:
        identity = c.dispatch(root)
        proposal = valid_proposal(c.pending[identity])
        c.edit_source({"d1": {"strict": True}})
        if scenario_id == "S12":
            c.edit_source({"d1": {"strict": False}})
        assert c.resolve(identity, proposal) == "discarded"
        assert c.records[root].stamp is None
    elif scenario_id == "S13":
        identity = c.dispatch(root)
        proposal = valid_proposal(c.pending[identity])
        assert c.resolve(identity, timeout=True) == "rejected"
        assert c.resolve(identity, proposal) == "discarded"
        assert c.resolve(identity, proposal) == "discarded"
        assert c.records[root].attempts == 1 and c.records[root].stamp is None
    elif scenario_id in {"S14", "S15"}:
        for _ in range(2):
            assert c.resolve(c.dispatch(root), {"invalid": True}) == "rejected"
        old = c.records[root].episode
        c.edit_source(deepcopy(c.documents))
        assert c.dispatch(root) is None
        assert c.records[root].attempts == 2 and c.records[root].episode == old
        assert len(c.suspended) == 3 and c.publish() == "rejected"
    elif scenario_id == "S16":
        count = len(c.history)
        # Contract change dirties architecture only; repaired bytes are equal.
        bindings = [replace(b, contract="v2") if b.stage == "architecture" else b for b in c.bindings]
        c.reconfigure(bindings)
        assert policy in c.suspended
        assert repair(c)
        assert len(c.history) == count + 1 and c._usable(policy)
    elif scenario_id == "S18":
        c.reconfigure([replace(b, contract="v2") if b.stage == "verification" else b for b in c.bindings])
        identity = c.dispatch(verification)
        assert c.resolve(identity, valid_proposal(c.pending[identity], "integer")) == "committed"
        assert all(c._usable(k) for k in c.active)
        assert c.publish() == "rejected"
    elif scenario_id == "S19":
        old_value = deepcopy(c.records[architecture].value)
        c.reconfigure([replace(b, contract="v2") if b.stage == "architecture" else b for b in c.bindings])
        identity = c.dispatch(architecture)
        proposal = valid_proposal(c.pending[identity], "integer")
        assert c.resolve(identity, proposal) == "rejected"
        assert c.events[-1]["validation"] is True and c.events[-1]["normalization"] is False
        assert c.records[architecture].value == old_value and not c._usable(architecture)
    elif scenario_id in {"S20", "S21"}:
        reviewer = Binding("security", 4, ("verification",), "security-worker")
        assert c.reconfigure(c.bindings + [reviewer]) == "committed"
        assert c.publish() == "rejected"
        if scenario_id == "S20":
            assert repair(c) and c.publish() == "published"
        else:
            # Make verification depend on the reviewer: new ranks remain acyclic.
            bindings = [replace(b, prerequisites=("security",), rank=5) if b.stage == "verification"
                        else replace(b, prerequisites=("implementation",)) if b.stage == "security" else b
                        for b in c.bindings]
            assert c.reconfigure(bindings) == "committed"
            before = c.snapshot()
            assert c.reconfigure([b for b in c.bindings if b.stage != "security"]) == "rejected"
            assert c.snapshot() == before
    elif scenario_id == "S22":
        identity = c.dispatch(root)
        proposal = valid_proposal(c.pending[identity])
        assert c.reconfigure(revoked={"requirements-worker"}) == "committed"
        assert c.resolve(identity, proposal) == "discarded" and root in c.suspended
    elif scenario_id == "S23":
        c.reconfigure([replace(b, contract="v2") if b.stage == "implementation" else b for b in c.bindings])
        identity = c.dispatch(policy)
        proposal = valid_proposal(c.pending[identity])
        c.reconfigure([replace(b, contract="v3") if b.stage == "implementation" else b for b in c.bindings])
        assert c.resolve(identity, proposal) == "discarded" and not c._usable(policy)
    elif scenario_id == "S24":
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda n: c.update_context(0, {str(n): {"document": "d1", "finding": str(n)}}), [1, 2]))
        assert sorted(outcomes) == ["committed", "conflict"] and c.context_version == 1
    elif scenario_id == "S25":
        checked = c.check_publication()
        c.edit_source({"d1": {"strict": True}})
        assert c.publish(checked) == "rejected" and c.published is None
    elif scenario_id == "S26":
        before = c.snapshot()
        assert c.observe() == "stutter" and c.snapshot() == before
        assert c.publish() == "published"
    elif scenario_id == "S27":
        before = c.snapshot()
        assert c.edit_source({"target:bad": {"strict": True}}) == "rejected"
        assert c.edit_source({"d1": {"strict": "true"}}) == "rejected"
        assert c.snapshot() == before
    elif scenario_id == "S28":
        # Separate extensional oracle: enumerate all six independent row outputs.
        tables_evaluated, event_words = 0, 0
        for h in (False, True):
            accepted = 0
            for outputs in product(product((200, 409), ("open", "archived")), repeat=6):
                tables_evaluated += 1
                rows = [{"state": s, "event": e, "status": out[0], "next": out[1]}
                        for (s, e), out in zip(product(("open", "archived"), ("read", "put", "archive")), outputs)]
                oracle = all(r["next"] == ("archived" if r["event"] == "archive" else r["state"])
                             and r["status"] == (409 if h and r["state"] == "archived" and r["event"] == "put" else 200)
                             for r in rows)
                assert validate_table(h, rows) == oracle
                accepted += int(oracle)
            assert accepted == 1
        for length in range(7):
            for word in product(("read", "put", "archive"), repeat=length):
                event_words += 1
                for state, event, status, successor in interpret(table(True), word):
                    assert state != "archived" or successor == "archived"
                    assert not (state == "archived" and event == "put") or status == 409
                    assert event != "archive" or successor == "archived"
        malformed = [[], table(True)[:-1], table(True) + [table(True)[0]], [table(True)[0]] * 6, None, {}]
        assert not any(validate_table(True, rows) for rows in malformed)
        c.experiment_metrics = {"policy_tables_enumerated": tables_evaluated,
                                "policy_event_words": event_words, "malformed_cases": len(malformed)}
    else:
        raise ValueError("unknown scenario: " + scenario_id)
    return c
