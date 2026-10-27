"""Independent event checker. Does not import controller or its validators."""
from copy import deepcopy
import json
from pathlib import Path


def encode(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def key(stage, document):
    return encode([stage, document])


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def validator(stage, o, v):
    if stage == "implementation":
        if not isinstance(v, list) or len(v) != 6:
            return False
        expected = {}
        for d in ("open", "archived"):
            for e in ("read", "put", "archive"):
                expected[d, e] = (409 if o["source"]["strict"] and d == "archived" and e == "put" else 200,
                                  "archived" if e == "archive" else d)
        actual = {}
        for row in v:
            if not isinstance(row, dict) or set(row) != {"state", "event", "status", "next"}:
                return False
            if not all(isinstance(row[f], str) for f in ("state", "event", "next")) or type(row["status"]) is not int:
                return False
            k = (row["state"], row["event"])
            if k in actual:
                return False
            actual[k] = (row["status"], row["next"])
        return actual == expected
    if stage == "requirements":
        return isinstance(v, dict) and type(v.get("strict")) is bool and v == {"clauses": ["R01", "R02", "R03"], "strict": o["source"]["strict"]}
    if stage == "architecture":
        return isinstance(v, dict) and set(v) == {"id_type", "operations"} and v["id_type"] in ("string", "integer") and v["operations"] == ["create", "read", "update", "archive", "list"]
    if stage == "verification":
        return isinstance(v, dict) and set(v) == {"id_type", "covered"} and v["id_type"] in ("string", "integer") and v["covered"] == ["R01", "R02", "R03"]
    if stage == "security":
        return v == {"assessed": ["create", "read", "update", "archive", "list"]}
    return False


def derive(state):
    """Build expected active observations from input and historical evidence."""
    active, suspended, usable, observations = set(), set(), set(), {}
    bindings = {b["stage"]: b for b in state["bindings"]}
    demand(len(bindings) == len(state["bindings"]), "duplicate producer")
    required = {"requirements", "architecture", "implementation", "verification"}
    demand(required <= set(bindings) <= required | {"security"}, "required view policy")
    for document, source in state["documents"].items():
        demand(isinstance(document, str) and not document.startswith("target:") and
               isinstance(source, dict) and set(source) == {"strict"} and type(source["strict"]) is bool, "source schema")
    ancestors = {}
    for b in sorted(state["bindings"], key=lambda b: (b["rank"], b["stage"])):
        demand(all(p in bindings and bindings[p]["rank"] < b["rank"] for p in b["prerequisites"]), "rank")
        ancestors[b["stage"]] = set(b["prerequisites"])
        for p in b["prerequisites"]:
            ancestors[b["stage"]].update(ancestors[p])
        needed = {"architecture": "requirements", "implementation": "architecture", "verification": "implementation", "security": "implementation"}.get(b["stage"])
        demand(needed is None or needed in ancestors[b["stage"]], "structural read ancestry")
        for document in state["documents"]:
            job = key(b["stage"], document)
            ready = (b["owner"] not in state["revoked"] and
                     (state["context_available"] or b["stage"] in ("requirements", "architecture")) and
                     all(key(p, document) in usable for p in b["prerequisites"]))
            if not ready:
                suspended.add(job)
                continue
            o = {"source": state["documents"][document] if b["stage"] in ("requirements", "implementation", "verification") else {},
                 "predecessors": {p: state["records"][key(p, document)]["value"] for p in b["prerequisites"]},
                 "context": {k: v for k, v in state["context"].items() if v["document"] == document}
                            if b["stage"] in ("implementation", "verification", "security") else {},
                 "contract": b["contract"], "owner": b["owner"], "schema": "document-service-v1", "stage": b["stage"]}
            observations[job] = encode(o)
            active.add(job)
            r = state["records"].get(job)
            demand(r is not None and r["signature"] == encode(o), "active signature")
            if r["stamp"] == encode(o) and r["evidence_owner"] == b["owner"]:
                usable.add(job)
    demand(active == set(state["active"]) and suspended == set(state["suspended"]), "active/suspended mismatch")
    return active, suspended, usable, observations


def check_state(s):
    active, suspended, usable, observations = derive(s)
    demand(s["nonce"] >= 0 and s["revision"] >= 0, "revision/nonce")
    for job, r in s["records"].items():
        demand(0 <= r["attempts"] <= s["budget"], "attempt bound")
        counted = [q for q in s["history"].values() if q["job"] == job and q["episode"] == r["episode"]]
        demand(len(counted) == r["attempts"], "history counting")
        demand(not r["failed"] or r["attempts"] == s["budget"], "failure memory")
        if r["stamp"] is not None:
            request = s["history"].get(r["evidence_request"])
            demand(request is not None and request["job"] == job and request["observation"] == r["stamp"] and request["owner"] == r["evidence_owner"], "acceptance provenance")
            o = json.loads(r["stamp"])
            demand(validator(json.loads(job)[0], o, r["value"]), "historical validation")
    grouped = {}
    for identity, q in s["history"].items():
        demand(identity == encode([q["job"], q["episode"], q["attempt"]]), "request identity")
        g = (q["job"], q["episode"])
        grouped.setdefault(g, []).append(q["attempt"])
    for attempts in grouped.values():
        demand(sorted(attempts) == list(range(1, len(attempts)+1)) and len(attempts) <= s["budget"], "episode count bound")
    for identity, q in s["pending"].items():
        demand(s["history"].get(identity) == q, "pending history")
        demand(q["job"] in active and q["observation"] == observations[q["job"]], "pending currentness")
        demand(q["episode"] == s["records"][q["job"]]["episode"], "pending episode")
    demand(len({q["job"] for q in s["pending"].values()}) == len(s["pending"]), "pending uniqueness")
    targets = {"target:" + encode(json.loads(j)) for j in active}
    demand(set(s["targets"]) == targets, "target coverage")
    for target, refs in s["references"].items():
        demand(target in targets and set(refs) <= targets, "reference integrity")
    return active, suspended, usable, observations


def normalized(candidate, old):
    """Independent executable reading of rank-order reconciliation, for effect checks."""
    c = deepcopy(candidate)
    c["active"], c["suspended"], c["targets"], c["references"] = [], [], [], {}
    usable, observations = set(), {}
    for b in sorted(c["bindings"], key=lambda b: (b["rank"], b["stage"])):
        for document in sorted(c["documents"]):
            job = key(b["stage"], document)
            available = (b["owner"] not in c["revoked"] and
                         (c["context_available"] or b["stage"] in ("requirements", "architecture")) and
                         all(key(p, document) in usable for p in b["prerequisites"]))
            if not available:
                c["suspended"].append(job)
                continue
            o = {"stage": b["stage"], "schema": "document-service-v1", "owner": b["owner"], "contract": b["contract"],
                 "source": c["documents"][document] if b["stage"] in ("requirements", "implementation", "verification") else {},
                 "predecessors": {p: c["records"][key(p, document)]["value"] for p in b["prerequisites"]},
                 "context": {k: v for k, v in c["context"].items() if v["document"] == document}
                            if b["stage"] in ("implementation", "verification", "security") else {}}
            signature = encode(o)
            record = c["records"].get(job)
            if record is None or job not in old["active"] or record["signature"] != signature:
                c["nonce"] += 1
                record = {"episode": c["nonce"], "signature": signature, "attempts": 0, "failed": False,
                          "value": record["value"] if record else None,
                          "stamp": record["stamp"] if record else None,
                          "evidence_owner": record["evidence_owner"] if record else None,
                          "evidence_request": record["evidence_request"] if record else None}
                c["records"][job] = record
            c["active"].append(job)
            observations[job] = signature
            if record["stamp"] == signature and record["evidence_owner"] == b["owner"]:
                usable.add(job)
            target = "target:" + job
            c["targets"].append(target)
            c["references"][target] = ["target:" + key(p, document) for p in b["prerequisites"]]
            if b["stage"] == "implementation":
                demand(c["records"][key("architecture", document)]["value"]["id_type"] == "string", "candidate structural failure")
    c["pending"] = {identity: q for identity, q in c["pending"].items() if
                    q["job"] in observations and q["observation"] == observations[q["job"]] and
                    q["episode"] == c["records"][q["job"]]["episode"] and
                    q["owner"] not in c["revoked"] and
                    q["owner"] == json.loads(observations[q["job"]])["owner"]}
    for field in ("active", "suspended", "targets"):
        c[field].sort()
    return c


def check_trace(trace):
    previous = trace["initial"]
    check_state(previous)
    allowed = {"EditSource", "UpdateContext", "Reconfigure", "Dispatch", "ResolveAccepted", "ResolveRejected", "Timeout", "DiscardObsoleteOrDuplicate", "Publish", "OptionalObservationStep"}
    for sequence, event in enumerate(trace["events"], 1):
        demand(event["event_sequence"] == sequence, "sequence gap")
        demand(event["before"] == previous, "state continuity")
        before, after = event["before"], event["after"]
        active, suspended, usable, observations = check_state(before)
        check_state(after)
        action, outcome = event["action"], event["outcome"]
        demand(action in allowed, "unknown action")
        demand(after["revision"] >= before["revision"] and after["nonce"] >= before["nonce"], "monotonicity")
        demand(all(after["history"].get(k) == v for k, v in before["history"].items()), "history mutated")
        if action == "Dispatch" and outcome == "dispatched":
            identity, job = event["request_id"], event["job_key"]
            demand(job in active - usable and not before["records"][job]["failed"], "dispatch guard")
            demand(identity not in before["history"] and identity in after["pending"], "fresh dispatch")
            expected = deepcopy(before)
            expected["records"][job]["attempts"] += 1
            expected["pending"][identity] = after["pending"][identity]
            expected["history"][identity] = after["pending"][identity]
            demand(after == expected, "dispatch effects")
        elif action in {"ResolveAccepted", "ResolveRejected", "Timeout"}:
            identity = event["request_id"]
            demand(identity in before["pending"] and identity not in after["pending"], "settlement activity")
            q = before["pending"][identity]
            job = q["job"]
            demand(q["owner"] not in before["revoked"] and q["observation"] == observations[job], "commit authority/currentness")
            demand(before["records"][job]["attempts"] == after["records"][job]["attempts"], "settlement budget")
            if action == "ResolveAccepted":
                demand(outcome == "committed" and event["validation"] and event["normalization"], "accept verdict")
                demand(validator(json.loads(job)[0], json.loads(q["observation"]), event["proposal"]), "accepted proposal")
                demand(after["records"][job]["value"] == event["proposal"] and after["records"][job]["evidence_request"] == identity, "accepted value/evidence")
                demand(after["revision"] == before["revision"] + 1, "commit revision")
                expected = deepcopy(before)
                r = expected["records"][job]
                r.update(value=event["proposal"], stamp=q["observation"], evidence_request=identity,
                         evidence_owner=q["owner"], failed=False)
                del expected["pending"][identity]
                expected["revision"] += 1
                demand(after == normalized(expected, before), "acceptance effects and unchanged fields")
            else:
                expected = deepcopy(before)
                del expected["pending"][identity]
                expected["records"][job]["failed"] = expected["records"][job]["attempts"] == expected["budget"]
                demand(after == expected, "rejection rollback")
        elif action == "Publish" and outcome == "published":
            demand(not suspended and not before["pending"] and active == usable, "publication completion")
            for document in before["documents"]:
                a, v = key("architecture", document), key("verification", document)
                if a in active and v in active:
                    demand(before["records"][a]["value"]["id_type"] == before["records"][v]["value"]["id_type"], "joint constraint")
            expected = deepcopy(before)
            expected["published"] = {"revision": before["revision"], "snapshot": before}
            demand(after == expected, "publication snapshot/revision")
        elif action in {"EditSource", "UpdateContext", "Reconfigure"} and outcome == "committed":
            demand(after["revision"] == before["revision"]+1, "edit revision")
            if action == "UpdateContext":
                demand(event["expected_version"] == before["context_version"] and after["context_version"] == before["context_version"]+1, "CAS")
            expected = deepcopy(before)
            if action == "EditSource":
                expected["documents"] = event["input"]
            elif action == "UpdateContext":
                expected["context"], expected["context_available"] = after["context"], after["context_available"]
                expected["context_version"] += 1
            else:
                expected["bindings"], expected["revoked"] = after["bindings"], after["revoked"]
                expected["configuration"] += 1
            expected["revision"] += 1
            demand(after == normalized(expected, before), "edit effects and unchanged fields")
            for job in set(before["active"]) & set(after["active"]):
                a, b = before["records"][job], after["records"][job]
                if a["signature"] == b["signature"]:
                    demand(a["episode"] == b["episode"] and a["attempts"] == b["attempts"], "unchanged budget reset")
                else:
                    demand(b["episode"] > before["nonce"] and b["attempts"] == 0, "new episode")
        else:
            demand(after == before, "unexpected non-stuttering action")
        previous = after
    return len(trace["events"])


def run():
    from scripts.common import ROOT, new_run, finish
    runs = sorted((ROOT / "results/raw").glob("*case-study*"))
    if not runs:
        raise ValueError("no case-study campaign")
    source = runs[-1]
    directory, manifest = new_run("conformance", {"source_run": source.name})
    results = []
    for path in sorted(source.glob("*.trace.json")):
        trace = json.loads(path.read_text())
        try:
            count = check_trace(trace)
            results.append({"trace": path.name, "status": "passed", "events": count})
        except Exception as error:
            results.append({"trace": path.name, "status": "failed", "reason": str(error)})
    # Corrupt genuine traces; the checker must reject them.
    original = json.loads((source / "S01.trace.json").read_text())
    corruptions = []
    for fault in ("unknown-action", "sequence-gap", "counter", "provenance", "publication-revision", "missing-event", "acceptance-source-deletion", "acceptance-context-change", "acceptance-contract-change"):
        t = deepcopy(original)
        if fault == "unknown-action":
            t["events"][0]["action"] = "UnspecifiedCommit"
        elif fault == "sequence-gap":
            t["events"][0]["event_sequence"] = 2
        elif fault == "counter":
            k = next(iter(t["events"][0]["after"]["active"]))
            t["events"][0]["after"]["records"][k]["attempts"] = 99
        elif fault == "provenance":
            e = next(e for e in t["events"] if e["action"] == "ResolveAccepted")
            k = t["events"][0]["job_key"]
            e["after"]["records"][k]["evidence_request"] = "forged"
        elif fault == "publication-revision":
            t["events"][-1]["after"]["published"]["revision"] = -1
        elif fault == "missing-event":
            del t["events"][0]
        elif fault == "acceptance-source-deletion":
            t["events"] = t["events"][:2]
            after = t["events"][-1]["after"]
            after["documents"], after["active"], after["suspended"], after["targets"], after["references"] = {}, [], [], [], {}
        else:
            t["events"] = t["events"][:2]
            after = t["events"][-1]["after"]
            if fault == "acceptance-context-change":
                after["context"] = {"unselected": {"document": "other", "finding": "injected"}}
            else:
                after["bindings"][-1]["contract"] = "injected"
        try:
            check_trace(t)
            rejected = False
        except (ValueError, KeyError):
            rejected = True
        corruptions.append({"fault": fault, "rejected": rejected})
        from scripts.common import write_json
        write_json(directory / (fault + ".trace.json"), t)
    status = "passed" if len(results) == 28 and all(r["status"] == "passed" for r in results) and all(c["rejected"] for c in corruptions) else "failed"
    return finish(directory, manifest, status, {"traces": results, "corruptions": corruptions,
                   "scope": "independent recorded guard/effect and deterministic reconciliation checks; not universal implementation refinement or log authenticity"})
