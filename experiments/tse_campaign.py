"""Randomized guard ablation (RQ1) and invalidation-cost comparison (RQ2).

Both campaigns drive the unmodified reference controller in src/vgc and
subclasses that change exactly one mechanism. Proposals come from scripted or
adversarial providers; no language model is called. Every number is a
deterministic function of the recorded seeds.

    python experiments/tse_campaign.py            # full campaign
    python experiments/tse_campaign.py --quick    # small smoke run
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import argparse
import hashlib
import json
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from vgc.controller import Controller  # noqa: E402
from vgc.observations import canonical, selected  # noqa: E402
from vgc.providers.scripted import valid_proposal  # noqa: E402
from vgc.scheduler import repair  # noqa: E402
from vgc.structure import allocate_resolve, check_bindings  # noqa: E402
from vgc.types import Binding, Record, Request  # noqa: E402
from vgc.validators import table, validate  # noqa: E402

SOURCE_STAGES = ("requirements", "implementation", "verification")
CONTEXT_STAGES = ("implementation", "verification", "security")
CORE_STAGES = ("requirements", "architecture", "implementation", "verification")
OWNERS = ("requirements-worker", "architecture-worker", "implementation-worker", "verification-worker")
REVIEWER = Binding("security", 4, ("verification",), "security-worker")

# One flag per removed mechanism; the paper's guard names are given alongside.
ABLATIONS = {
    "full": ((), "Reference controller (all guards)"),
    "no-cancel": (("cancel",), "Request cancellation on reconcile"),
    "no-recheck": (("recheck",), "Commit-time signature recheck"),
    "no-obsolete": (("cancel", "recheck"), "Both obsolete-response defences"),
    "no-contract": (("contract",), "Contract identity in signature"),
    "no-context": (("context",), "Selected context in footprint"),
    "no-upstream": (("upstream",), "Upstream usability gate"),
    "no-authority": (("authority",), "Authority check"),
    "no-budget": (("budget",), "Persistent episode budget"),
    "no-candidate": (("structure",), "Candidate normalization"),
    "no-global": (("global",), "Global publication predicate"),
}
PROPERTIES = {
    "stale": "Obsolete or unavailable input exposed as usable",
    "invalid": "Value invalid for its current observation exposed",
    "upstream": "Value exposed while a prerequisite is unusable",
    "authority": "Value from a revoked owner exposed",
    "structure": "Ill-typed structure installed",
    "budget": "More than k requests in one dependency episode",
    "publish": "Snapshot published that violates the barrier",
}


class Lean(Controller):
    """Keeps admission logic; stores action names instead of state snapshots."""

    def _event(self, action, before, outcome, **data):
        self.events.append(action)
        return outcome

    def _candidate(self):
        # Controller._candidate instantiates the base class; keep the subclass so
        # overridden observation/reconcile logic also governs private candidates.
        # The request history is append-only with frozen records and candidates never
        # write it, so it is shared instead of copied (copying made cost runs quadratic).
        candidate = object.__new__(type(self))
        candidate.__dict__ = {k: deepcopy(v) for k, v in self.__dict__.items()
                              if k not in ("lock", "events", "initial", "history")}
        candidate.lock, candidate.events, candidate.history = self.lock, self.events, self.history
        return candidate

    def _install(self, candidate):
        for key, value in candidate.__dict__.items():
            if key not in ("lock", "events"):
                setattr(self, key, value)


class Ablated(Lean):
    """Reference controller with selected mechanisms removed (see ABLATIONS)."""

    def __init__(self, documents=None, budget=2, flags=()):
        self.flags = frozenset(flags)
        super().__init__(documents, budget)

    def _usable(self, key):
        record = self.records.get(key)
        if key not in self.active or record is None:
            return False
        stage, _ = self.split(key)
        ok = record.stamp == record.signature and record.evidence_owner == self._binding(stage).owner
        return ok and ("authority" in self.flags or record.evidence_owner not in self.revoked)

    def observation(self, b, document):
        if b.owner in self.revoked and "authority" not in self.flags:
            return None
        if b.stage in CONTEXT_STAGES and not self.context_available:
            return None
        predecessors = {}
        for stage in b.prerequisites:
            key = self.key(stage, document)
            record = self.records.get(key)
            if "upstream" in self.flags:
                # Consume whatever bytes are stored, fresh or not.
                if record is None or record.value is None:
                    return None
            elif not self._usable(key):
                return None
            predecessors[stage] = deepcopy(record.value)
        source = self.documents[document] if b.stage in SOURCE_STAGES else {}
        context = selected(self.context, document) if b.stage in CONTEXT_STAGES and "context" not in self.flags else {}
        observation = {"source": deepcopy(source), "predecessors": predecessors, "context": deepcopy(context),
                       "owner": b.owner, "schema": "document-service-v1", "stage": b.stage}
        if "contract" not in self.flags:
            observation["contract"] = b.contract
        return observation

    def _reconcile(self):
        # Mirrors Controller._reconcile; each flag disables one marked step.
        by_stage = check_bindings(self.bindings)
        required = set(CORE_STAGES)
        if not required <= set(by_stage) or not set(by_stage) <= required | {"security"}:
            raise ValueError("configuration must retain the document-service core views")
        ancestors = {}
        for b in sorted(self.bindings, key=lambda b: (b.rank, b.stage)):
            ancestors[b.stage] = set(b.prerequisites)
            for p in b.prerequisites:
                ancestors[b.stage].update(ancestors[p])
        for stage, prerequisite in (("architecture", "requirements"), ("implementation", "architecture"),
                                    ("verification", "implementation"), ("security", "implementation")):
            if stage in by_stage and prerequisite not in ancestors[stage]:
                raise ValueError("missing declared structural dependency: " + prerequisite)
        previous = self.active.copy()
        self.active, self.suspended = set(), set()
        keys, refs = [], {}
        for b in sorted(self.bindings, key=lambda b: (b.rank, b.stage)):
            for document in sorted(self.documents):
                key = self.key(b.stage, document)
                observation = self.observation(b, document)
                if observation is None:
                    self.suspended.add(key)
                    continue
                self.active.add(key)
                signature = canonical(observation)
                old = self.records.get(key)
                if old is None or old.signature != signature or key not in previous:
                    self.nonce += 1
                    record = Record(self.nonce, signature)
                    if old is not None:
                        record.value, record.stamp = deepcopy(old.value), old.stamp
                        record.evidence_owner, record.evidence_request = old.evidence_owner, old.evidence_request
                    self.records[key] = record
                elif "budget" in self.flags:
                    # Ablation: every controller pass grants a fresh budget.
                    old.attempts, old.failed = 0, False
                keys.append((b.stage, document))
                refs[(b.stage, document)] = tuple((p, document) for p in b.prerequisites)
                if b.stage == "implementation" and "structure" not in self.flags:
                    architecture = self.records[self.key("architecture", document)].value
                    if architecture["id_type"] != "string":
                        raise ValueError("document identity expression requires string")
        self.targets, self.references = allocate_resolve(keys, refs)
        if "cancel" in self.flags:
            return
        for identity, request in list(self.pending.items()):
            r = self.records.get(request.job)
            if (request.job not in self.active or r.episode != request.episode or
                    r.signature != request.observation or
                    (request.owner in self.revoked and "authority" not in self.flags) or
                    request.owner != self._binding(self.split(request.job)[0]).owner):
                del self.pending[identity]

    def dispatch(self, key):
        if "budget" not in self.flags:
            return super().dispatch(key)
        # A reset counter would recreate (job, episode, attempt) identities, which the
        # base controller refuses; isolate the budget mechanism with unique identities.
        with self.lock:
            r = self.records.get(key)
            if (key not in self.active or self._usable(key) or r.failed or r.attempts >= self.budget or
                    any(p.job == key for p in self.pending.values())):
                return None
            r.attempts += 1
            identity = canonical([key, r.episode, r.attempts, len(self.history)])
            request = Request(identity, key, r.episode, r.attempts, r.signature,
                              self._binding(self.split(key)[0]).owner)
            self.pending[identity] = self.history[identity] = request
            return identity

    def resolve(self, identity, value=None, timeout=False):
        with self.lock:
            request = self.pending.get(identity)
            if request is None:
                return self._event("DiscardObsoleteOrDuplicate", None, "discarded")
            r = self.records[request.job]
            stage, document = self.split(request.job)
            if request.job not in self.active:
                # Even a naive coordinator cannot write a slot that no longer exists.
                del self.pending[identity]
                return self._event("DiscardObsoleteOrDuplicate", None, "discarded")
            current = self.observation(self._binding(stage), document)
            if "recheck" in self.flags:
                # Naive admission: any in-flight answer is taken to answer the current question.
                observation = json.loads(request.observation)
                stale = False
            else:
                observation = current
                stale = (current is None or request.episode != r.episode or
                         request.observation != canonical(current))
            if "authority" not in self.flags:
                stale = stale or request.owner in self.revoked or request.owner != self._binding(stage).owner
            if stale:
                del self.pending[identity]
                return self._event("DiscardObsoleteOrDuplicate", None, "discarded")
            valid = not timeout and validate(stage, observation, value)
            if valid:
                c = self._candidate()
                cr = c.records[request.job]
                cr.value = deepcopy(value)
                cr.stamp = cr.signature if "recheck" in self.flags else request.observation
                cr.evidence_owner, cr.evidence_request = request.owner, identity
                cr.failed = False
                del c.pending[identity]
                c.revision += 1
                try:
                    c._reconcile()
                except ValueError:
                    pass
                else:
                    self._install(c)
                    return self._event("ResolveAccepted", None, "committed")
            del self.pending[identity]
            r.failed = r.attempts == self.budget
            return self._event("ResolveRejected", None, "rejected")

    def check_publication(self):
        with self.lock:
            ready = not self.suspended and not self.pending and all(self._usable(k) for k in self.active)
            ok = ready
            if ready and "global" not in self.flags:
                for document in self.documents:
                    a, v = self.key("architecture", document), self.key("verification", document)
                    if a in self.active and v in self.active:
                        ok &= self.records[a].value["id_type"] == self.records[v].value["id_type"]
            return {"revision": self.revision, "snapshot": self.snapshot(), "ok": bool(ok)}


class Oracle:
    """Independent specification-level judge of every reachable state.

    It recomputes effective observations from authoritative inputs, remembers the
    observation each request was dispatched against, and tracks dependency
    episodes itself. It never consults the controller's signatures or flags.
    """

    def __init__(self, budget):
        self.budget = budget
        self.dispatched = {}
        self.episode = {}
        self.counts = Counter()

    def _binding(self, c, stage):
        return next((b for b in c.bindings if b.stage == stage), None)

    def observation(self, c, stage, document, memo):
        if (stage, document) in memo:
            return memo[stage, document]
        b = self._binding(c, stage)
        result = None
        if (b is not None and document in c.documents and b.owner not in c.revoked and
                (stage not in CONTEXT_STAGES or c.context_available)):
            predecessors = {}
            for p in b.prerequisites:
                if not self.usable(c, p, document, memo):
                    break
                predecessors[p] = c.records[c.key(p, document)].value
            else:
                result = canonical({"source": c.documents[document] if stage in SOURCE_STAGES else {},
                                    "predecessors": predecessors,
                                    "context": selected(c.context, document) if stage in CONTEXT_STAGES else {},
                                    "contract": b.contract, "owner": b.owner, "stage": stage})
        memo[stage, document] = result
        return result

    def usable(self, c, stage, document, memo):
        observation = self.observation(c, stage, document, memo)
        record = c.records.get(c.key(stage, document))
        return (observation is not None and record is not None and record.evidence_request is not None and
                self.dispatched.get(record.evidence_request) == observation and
                validate(stage, json.loads(observation), record.value))

    def jobs(self, c):
        return [(b.stage, d) for b in c.bindings for d in sorted(c.documents)]

    def advance(self, c):
        """Start a new episode for every job whose effective observation changed."""
        memo = {}
        for job in self.jobs(c):
            observation = self.observation(c, *job, memo)
            previous = self.episode.get(job)
            if observation is None:
                self.episode[job] = (None, previous[1] if previous else 0)
            elif previous is None or previous[0] != observation:
                self.episode[job] = (observation, (previous[1] if previous else 0) + 1)

    def on_dispatch(self, c, identity, key):
        """Return the violated property, if any, for one dispatched request."""
        job = tuple(c.split(key))
        observation = self.observation(c, *job, {})
        self.dispatched[identity] = observation
        if observation is None:
            return "stale"  # an unavailable or unauthorized input was sent to a worker
        episode = self.episode[job][1]
        self.counts[job, episode] += 1
        return "budget" if self.counts[job, episode] > self.budget else None

    def exposed(self, c):
        """Violations among values the controller lets consumers read."""
        found, memo = set(), {}
        for key in c.active:
            if not c._usable(key):
                continue
            stage, document = c.split(key)
            b = self._binding(c, stage)
            record = c.records[key]
            if b is None or b.owner in c.revoked or record.evidence_owner in c.revoked:
                found.add("authority")
                continue
            if any(not self.usable(c, p, document, memo) for p in b.prerequisites):
                found.add("upstream")
                continue
            observation = self.observation(c, stage, document, memo)
            # Provenance and validity are judged separately: a stale value can still happen to be valid.
            if observation is None or self.dispatched.get(record.evidence_request) != observation:
                found.add("stale")
            if observation is not None and not validate(stage, json.loads(observation), record.value):
                found.add("invalid")
            # Structural typing binds only active consumers; a suspended stage has no references.
            if (stage == "architecture" and isinstance(record.value, dict) and
                    record.value.get("id_type") != "string" and c.key("implementation", document) in c.active):
                found.add("structure")
        return found

    def publication_ok(self, c):
        memo = {}
        for stage, document in self.jobs(c):
            if not self.usable(c, stage, document, memo):
                return False
        for document in c.documents:
            a = c.records[c.key("architecture", document)].value
            v = c.records[c.key("verification", document)].value
            if a["id_type"] != "string" or a["id_type"] != v["id_type"]:
                return False
        return True


def adversarial(rng, request):
    stage = json.loads(request.observation)["stage"]
    roll = rng.random()
    if roll < 0.62:
        return valid_proposal(request)
    if roll < 0.76:
        return valid_proposal(request, "integer") if stage in ("architecture", "verification") else valid_proposal(request)
    if roll < 0.89:
        return {"malformed": True}
    # Plausible but answering a different policy question.
    strict = json.loads(request.observation)["source"].get("strict")
    if stage == "implementation" and strict is not None:
        return table(not strict)
    if stage == "requirements" and strict is not None:
        return {"clauses": ["R01", "R02", "R03"], "strict": not strict}
    return valid_proposal(request)


ACTIONS = (("dispatch", 26), ("deliver", 26), ("timeout", 4), ("edit", 7), ("context", 7),
           ("contract", 4), ("revoke", 3), ("reviewer", 2), ("publish", 6), ("drain", 6), ("settle", 6))


def ablation_run(variant, seed, steps, budget=2, max_documents=3):
    rng = random.Random(seed)
    documents = {"d%d" % i: {"strict": rng.random() < 0.5} for i in range(1, rng.randint(1, max_documents) + 1)}
    # The reference run uses the unmodified admission code (only event storage differs).
    c = Lean(documents, budget) if variant == "full" else Ablated(documents, budget, ABLATIONS[variant][0])
    oracle = Oracle(budget)
    oracle.advance(c)
    inflight, first, publications, dispatches, exceptions = [], {}, 0, 0, 0
    names, weights = zip(*ACTIONS)
    next_doc = len(documents) + 1

    def eligible():
        return [k for k in sorted(c.active) if not c._usable(k) and not c.records[k].failed
                and c.records[k].attempts < c.budget and not any(p.job == k for p in c.pending.values())]

    def dispatch(key):
        nonlocal dispatches
        identity = c.dispatch(key)
        if identity is None:
            return None
        dispatches += 1
        violated = oracle.on_dispatch(c, identity, key)
        if violated:
            first.setdefault(violated, step)
        return identity

    def judge():
        # Called after every transaction so no intermediate state escapes the oracle.
        oracle.advance(c)
        for prop in oracle.exposed(c):
            first.setdefault(prop, step)

    def resolve(identity, value=None, timeout=False):
        c.resolve(identity, value, timeout)
        judge()

    def publish():
        nonlocal publications
        if c.publish() == "published":
            publications += 1
            if not oracle.publication_ok(c):
                first.setdefault("publish", step)

    for step in range(1, steps + 1):
        action = rng.choices(names, weights)[0]
        if action == "dispatch":
            jobs = eligible()
            if jobs:
                identity = dispatch(rng.choice(jobs))
                if identity is not None:
                    inflight.append((identity, adversarial(rng, c.pending[identity])))
        elif action in ("deliver", "timeout") and inflight:
            index = rng.randrange(len(inflight))
            identity, value = inflight[index]
            if action == "timeout":
                resolve(identity, timeout=True)
                if rng.random() < 0.5:
                    inflight.pop(index)
            else:
                resolve(identity, value)
                if rng.random() >= 0.2:
                    inflight.pop(index)
        elif action in ("drain", "settle"):
            if action == "settle":
                # Deliver every in-flight reply in random order before repairing.
                rng.shuffle(inflight)
                for identity, value in inflight:
                    resolve(identity, value)
                inflight.clear()
            # Cooperative bursts: dispatch every eligible job and answer at once,
            # usually well but occasionally with a locally valid integer identifier.
            for _ in range(4 if action == "settle" else 1):
                for key in eligible():
                    identity = dispatch(key)
                    if identity is not None:
                        id_type = "integer" if rng.random() < 0.15 else "string"
                        resolve(identity, valid_proposal(c.pending[identity], id_type))
            if action == "settle":
                publish()
        elif action == "edit":
            docs = deepcopy(c.documents)
            roll = rng.random()
            if roll < 0.15 and len(docs) < max_documents + 1:
                docs["d%d" % next_doc] = {"strict": rng.random() < 0.5}
                next_doc += 1
            elif roll < 0.3 and len(docs) > 1:
                docs.pop(rng.choice(sorted(docs)))
            else:
                d = rng.choice(sorted(docs))
                docs[d]["strict"] = not docs[d]["strict"]
            c.edit_source(docs)
        elif action == "context":
            context = deepcopy(c.context)
            roll = rng.random()
            available = c.context_available
            if roll < 0.35:
                target = rng.choice(sorted(c.documents) + ["outside"])
                context["f%d" % rng.randint(1, 4)] = {"document": target, "finding": rng.choice(("path", "auth", "log"))}
            elif roll < 0.55 and context:
                context.pop(rng.choice(sorted(context)))
            elif roll < 0.85:
                pass  # equal content at a new version
            else:
                available = not available
            version = c.context_version if rng.random() < 0.9 else c.context_version - 1
            try:
                c.update_context(version, context, available)
            except ValueError:
                # A public action must record a rejection, never raise (see report).
                exceptions += 1
        elif action == "contract":
            stage = rng.choice([b.stage for b in c.bindings])
            c.reconfigure([replace(b, contract="v%d" % rng.randint(1, 3)) if b.stage == stage else b
                           for b in c.bindings])
        elif action == "revoke":
            c.reconfigure(revoked=set() if c.revoked else {rng.choice(OWNERS)})
        elif action == "reviewer":
            stages = {b.stage for b in c.bindings}
            c.reconfigure([b for b in c.bindings if b.stage != "security"] if "security" in stages
                          else c.bindings + [REVIEWER])
        elif action == "publish":
            publish()
        judge()
    return {"variant": variant, "seed": seed, "first_violation": first, "publications": publications,
            "dispatches": dispatches, "documents": len(documents), "api_exceptions": exceptions}


def ablation_campaign(runs, steps, seed0=20261027):
    results = {}
    for variant in ABLATIONS:
        started = time.monotonic()
        rows = [ablation_run(variant, seed0 + i, steps) for i in range(runs)]
        violated = {p: sum(p in r["first_violation"] for r in rows) for p in PROPERTIES}
        steps_to = {p: sorted(r["first_violation"][p] for r in rows if p in r["first_violation"]) for p in PROPERTIES}
        results[variant] = {
            "removed": ABLATIONS[variant][1], "flags": list(ABLATIONS[variant][0]), "runs": runs,
            "runs_violating": violated,
            "runs_with_any_violation": sum(bool(r["first_violation"]) for r in rows),
            "median_first_violation_step": {p: s[len(s) // 2] if s else None for p, s in steps_to.items()},
            "runs_publishing": sum(r["publications"] > 0 for r in rows),
            "publications": sum(r["publications"] for r in rows),
            "dispatches": sum(r["dispatches"] for r in rows),
            "runs_with_api_exception": sum(r["api_exceptions"] > 0 for r in rows),
            "elapsed_seconds": time.monotonic() - started,
        }
        print("ablation", variant, results[variant]["runs_with_any_violation"], "/", runs, flush=True)
    return results


# ---------------------------------------------------------------- RQ2: cost

STRATEGIES = {
    "exact": "Exact effective footprint (this paper)",
    "no-cutoff": "No early cutoff (upstream acceptance identity)",
    "version": "Version-keyed shared context",
    "workspace": "Whole-workspace footprint",
    "full": "Full regeneration on every input change",
}


class Strategy(Lean):
    """Same validators, scheduler and guards; only the observation function differs."""

    def __init__(self, documents, budget=2, mode="exact"):
        self.mode, self.input_revision = mode, 0
        self.sent_requests, self.sent_bytes = 0, 0
        super().__init__(documents, budget)

    def _event(self, action, before, outcome, **data):
        return outcome

    def snapshot(self):
        return None

    def observation(self, b, document):
        o = super().observation(b, document)
        if o is None or self.mode == "exact":
            return o
        if self.mode in ("no-cutoff", "full"):
            o["predecessors"] = {p: self.records[self.key(p, document)].evidence_request for p in b.prerequisites}
        if self.mode == "version" and b.stage in CONTEXT_STAGES:
            o["context_version"] = self.context_version
        if self.mode == "workspace":
            # Every worker sees the whole shared workspace (validators still read their own slice).
            o["workspace"] = {"documents": deepcopy(self.documents), "context": deepcopy(self.context)}
        if self.mode == "full":
            o["input_revision"] = self.input_revision
        return o

    def edit_source(self, documents):
        self.input_revision += 1
        return super().edit_source(documents)

    def update_context(self, expected_version, context, available=True):
        self.input_revision += 1
        return super().update_context(expected_version, context, available)

    def reconfigure(self, bindings=None, revoked=None):
        self.input_revision += 1
        return super().reconfigure(bindings, revoked)

    def dispatch(self, key):
        identity = super().dispatch(key)
        if identity is not None:
            self.sent_requests += 1
            self.sent_bytes += len(self.pending[identity].observation)
        return identity


CHANGES = ("source", "context-selected", "context-unselected", "context-equal", "contract")


def change_stream(rng, documents, length):
    stream = []
    for _ in range(length):
        kind = rng.choices(CHANGES, (35, 15, 10, 10, 30))[0]
        stream.append((kind, rng.choice(sorted(documents)), rng.choice(CORE_STAGES), rng.randint(0, 10 ** 6)))
    return stream


def apply_change(c, change):
    kind, document, stage, salt = change
    if kind == "source":
        docs = deepcopy(c.documents)
        docs[document]["strict"] = not docs[document]["strict"]
        return c.edit_source(docs)
    if kind.startswith("context"):
        context = deepcopy(c.context)
        if kind == "context-selected":
            context["f-" + document] = {"document": document, "finding": "finding-%d" % salt}
        elif kind == "context-unselected":
            context["f-outside"] = {"document": "outside", "finding": "finding-%d" % salt}
        return c.update_context(c.context_version, context)
    b = next(b for b in c.bindings if b.stage == stage)
    return c.reconfigure([replace(x, contract="c%d" % salt) if x is b else x for x in c.bindings])


def cost_run(n, seed, changes):
    rng = random.Random(seed)
    documents = {"d%02d" % i: {"strict": rng.random() < 0.5} for i in range(n)}
    context = {"f-" + d: {"document": d, "finding": "initial"} for d in documents if rng.random() < 0.5}
    stream = change_stream(rng, documents, changes)
    out, finals = {}, {}
    for mode in STRATEGIES:
        c = Strategy(documents, 2, mode)
        c.update_context(0, context)
        assert repair(c)
        per_kind = {k: [0, 0, 0] for k in CHANGES}  # changes, requests, bytes
        values = []
        for change in stream:
            requests, size = c.sent_requests, c.sent_bytes
            assert apply_change(c, change) == "committed"
            assert repair(c), (mode, change)
            per_kind[change[0]][0] += 1
            per_kind[change[0]][1] += c.sent_requests - requests
            per_kind[change[0]][2] += c.sent_bytes - size
            values.append({k: canonical(r.value) for k, r in c.records.items() if k in c.active})
        out[mode] = per_kind
        finals[mode] = values
    # Coarser footprints must never change the accepted outcome, only its cost.
    equivalent = all(finals[m] == finals["exact"] for m in STRATEGIES)
    return {"n": n, "seed": seed, "per_kind": out, "outcome_equivalent": equivalent}


def cost_campaign(sizes, seeds, changes, seed0=7000):
    results = []
    for n in sizes:
        started = time.monotonic()
        for i in range(seeds):
            results.append(cost_run(n, seed0 + 101 * n + i, changes))
        print("cost n=%d %.1fs" % (n, time.monotonic() - started), flush=True)
    summary = {}
    for n in sizes:
        rows = [r for r in results if r["n"] == n]
        summary[str(n)] = {}
        for mode in STRATEGIES:
            totals = {k: [sum(r["per_kind"][mode][k][i] for r in rows) for i in range(3)] for k in CHANGES}
            count = sum(t[0] for t in totals.values())
            summary[str(n)][mode] = {
                "requests_per_change": sum(t[1] for t in totals.values()) / count,
                "kbytes_per_change": sum(t[2] for t in totals.values()) / count / 1000,
                "by_kind": {k: {"changes": t[0], "requests_per_change": t[1] / t[0] if t[0] else None,
                                "bytes_per_request": t[2] / t[1] if t[1] else None} for k, t in totals.items()},
            }
    return {"runs": results, "summary": summary,
            "all_outcomes_equivalent": all(r["outcome_equivalent"] for r in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    config = ({"ablation_runs": 20, "ablation_steps": 60, "sizes": [1, 2, 4], "seeds": 2, "changes": 10} if args.quick else
              {"ablation_runs": 300, "ablation_steps": 120, "sizes": [1, 2, 4, 8, 16, 32], "seeds": 5, "changes": 40})
    started = time.monotonic()
    ablation = ablation_campaign(config["ablation_runs"], config["ablation_steps"])
    cost = cost_campaign(config["sizes"], config["seeds"], config["changes"])
    sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
               for p in sorted(str(x.relative_to(ROOT).as_posix()) for x in (ROOT / "src/vgc").rglob("*.py"))
               + ["experiments/tse_campaign.py"]}
    report = {"config": config, "quick": args.quick, "python": platform.python_version(),
              "platform": platform.platform(), "elapsed_seconds": time.monotonic() - started,
              "source_sha256": sources, "actions": dict(ACTIONS), "properties": PROPERTIES,
              "strategies": STRATEGIES, "ablation": ablation,
              "cost": {"summary": cost["summary"], "all_outcomes_equivalent": cost["all_outcomes_equivalent"],
                       "runs": [{k: v for k, v in r.items()} for r in cost["runs"]]}}
    out = ROOT / "results/processed/tse" / ("campaign-quick.json" if args.quick else "campaign.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(out.relative_to(ROOT))
    full = ablation["full"]
    return int(full["runs_with_any_violation"] != 0 or not cost["all_outcomes_equivalent"])


if __name__ == "__main__":
    raise SystemExit(main())
