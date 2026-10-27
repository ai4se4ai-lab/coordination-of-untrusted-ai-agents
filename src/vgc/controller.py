"""Serialized atomic transactions with private candidate normalization.

Nonces are unique for one Controller lifetime only. Proposals never execute.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from threading import RLock
import json

from .types import Binding, Record, Request
from .observations import canonical, selected
from .structure import check_bindings, allocate_resolve
from .validators import validate


def default_bindings():
    return [Binding("requirements", 0, (), "requirements-worker"),
            Binding("architecture", 1, ("requirements",), "architecture-worker"),
            Binding("implementation", 2, ("architecture",), "implementation-worker"),
            Binding("verification", 3, ("implementation",), "verification-worker")]


class Controller:
    def __init__(self, documents=None, budget=2):
        if type(budget) is not int or budget < 1:
            raise ValueError("positive integer budget required")
        self.lock = RLock()
        self.budget = budget
        self.documents = deepcopy(documents if documents is not None else {"d1": {"strict": False}})
        self._check_source(self.documents)
        self.bindings = default_bindings()
        self.context, self.context_version = {}, 0
        self.context_available = True
        self.revoked = set()
        self.records, self.active, self.suspended = {}, set(), set()
        self.pending, self.history = {}, {}
        self.nonce, self.revision, self.configuration = 0, 0, 0
        self.published = None
        self.events = []
        self.targets, self.references = {}, {}
        self._reconcile()
        self.initial = self.snapshot()

    @staticmethod
    def key(stage, document):
        return canonical([stage, document])

    @staticmethod
    def split(key):
        return json.loads(key)

    @staticmethod
    def _check_source(documents):
        if not isinstance(documents, dict):
            raise ValueError("source must be a mapping")
        for key, value in documents.items():
            if (not isinstance(key, str) or key.startswith("target:") or
                    not isinstance(value, dict) or set(value) != {"strict"} or
                    type(value["strict"]) is not bool):
                raise ValueError("invalid source delta or target namespace")

    def _binding(self, stage):
        return next(b for b in self.bindings if b.stage == stage)

    def _usable(self, key):
        record = self.records.get(key)
        if key not in self.active or record is None:
            return False
        stage, _ = self.split(key)
        return (record.stamp == record.signature and record.evidence_owner == self._binding(stage).owner
                and record.evidence_owner not in self.revoked)

    def observation(self, b, document):
        if b.owner in self.revoked:
            return None
        if b.stage in ("implementation", "verification", "security") and not self.context_available:
            return None
        predecessors = {}
        for stage in b.prerequisites:
            key = self.key(stage, document)
            if not self._usable(key):
                return None
            predecessors[stage] = deepcopy(self.records[key].value)
        # Requirements and policy must observe the business clause even when API is unchanged.
        source = self.documents[document] if b.stage in ("requirements", "implementation", "verification") else {}
        context = selected(self.context, document) if b.stage in ("implementation", "verification", "security") else {}
        return {"source": deepcopy(source), "predecessors": predecessors,
                "context": deepcopy(context), "contract": b.contract, "owner": b.owner,
                "schema": "document-service-v1", "stage": b.stage}

    def _reconcile(self):
        by_stage = check_bindings(self.bindings)
        required = {"requirements", "architecture", "implementation", "verification"}
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
                keys.append((b.stage, document))
                refs[(b.stage, document)] = tuple((p, document) for p in b.prerequisites)
                # Concrete downstream structural condition, checked on every candidate.
                if b.stage == "implementation":
                    architecture = self.records[self.key("architecture", document)].value
                    if architecture["id_type"] != "string":
                        raise ValueError("document identity expression requires string")
        self.targets, self.references = allocate_resolve(keys, refs)
        for identity, request in list(self.pending.items()):
            r = self.records.get(request.job)
            if (request.job not in self.active or r.episode != request.episode or
                    r.signature != request.observation or request.owner in self.revoked or
                    request.owner != self._binding(self.split(request.job)[0]).owner):
                del self.pending[identity]

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        return deepcopy({"documents": self.documents, "bindings": [asdict(b) for b in self.bindings],
                         "context": self.context, "context_version": self.context_version,
                         "context_available": self.context_available, "revoked": sorted(self.revoked),
                         "records": {k: asdict(r) for k, r in self.records.items()},
                         "active": sorted(self.active), "suspended": sorted(self.suspended),
                         "pending": {k: asdict(r) for k, r in self.pending.items()},
                         "history": {k: asdict(r) for k, r in self.history.items()},
                         "nonce": self.nonce, "revision": self.revision,
                         "configuration": self.configuration, "budget": self.budget,
                         "published": self.published,
                         "targets": sorted(self.targets.values()),
                         "references": {k: list(v) for k, v in self.references.items()}})

    def _event(self, action, before, outcome, **data):
        self.events.append({"event_sequence": len(self.events) + 1, "action": action,
                            "outcome": outcome, "before": before, "after": self.snapshot(), **deepcopy(data)})
        return outcome

    def _candidate(self):
        candidate = object.__new__(Controller)
        candidate.__dict__ = {k: deepcopy(v) for k, v in self.__dict__.items()
                              if k not in ("lock", "events", "initial")}
        candidate.lock = self.lock
        return candidate

    def _install(self, candidate):
        for key, value in candidate.__dict__.items():
            if key != "lock":
                setattr(self, key, value)

    def edit_source(self, documents):
        with self.lock:
            before = self.snapshot()
            try:
                self._check_source(documents)
                c = self._candidate()
                c.documents = deepcopy(documents)
                c.revision += 1
                c._reconcile()
                self._install(c)
            except ValueError as error:
                return self._event("EditSource", before, "rejected", reason=str(error))
            return self._event("EditSource", before, "committed", input=documents)

    def update_context(self, expected_version, context, available=True):
        with self.lock:
            before = self.snapshot()
            if expected_version != self.context_version:
                return self._event("UpdateContext", before, "conflict")
            if (not isinstance(context, dict) or type(available) is not bool or
                    any(not isinstance(k, str) or not isinstance(v, dict) or
                        set(v) != {"document", "finding"} or
                        not isinstance(v["document"], str) or not isinstance(v["finding"], str)
                        for k, v in context.items())):
                return self._event("UpdateContext", before, "rejected")
            c = self._candidate()
            c.context, c.context_available = deepcopy(context), available
            c.context_version += 1
            c.revision += 1
            c._reconcile()
            self._install(c)
            return self._event("UpdateContext", before, "committed", expected_version=expected_version)

    def reconfigure(self, bindings=None, revoked=None):
        with self.lock:
            before = self.snapshot()
            c = self._candidate()
            if bindings is not None:
                c.bindings = list(bindings)
            if revoked is not None:
                c.revoked = set(revoked)
            try:
                c.configuration += 1
                c.revision += 1
                c._reconcile()
            except ValueError as error:
                return self._event("Reconfigure", before, "rejected", reason=str(error))
            self._install(c)
            return self._event("Reconfigure", before, "committed")

    def dispatch(self, key):
        with self.lock:
            before = self.snapshot()
            r = self.records.get(key)
            if (key not in self.active or self._usable(key) or r.failed or r.attempts >= self.budget or
                    any(p.job == key for p in self.pending.values())):
                self._event("Dispatch", before, "ineligible", job_key=key)
                return None
            r.attempts += 1
            identity = canonical([key, r.episode, r.attempts])
            owner = self._binding(self.split(key)[0]).owner
            request = Request(identity, key, r.episode, r.attempts, r.signature, owner)
            if identity in self.history:
                raise AssertionError("request identity reused")
            self.pending[identity] = self.history[identity] = request
            self._event("Dispatch", before, "dispatched", job_key=key, request_id=identity)
            return identity

    def resolve(self, identity, value=None, timeout=False):
        with self.lock:
            before = self.snapshot()
            request = self.pending.get(identity)
            if request is None:
                return self._event("DiscardObsoleteOrDuplicate", before, "discarded", request_id=identity)
            r = self.records[request.job]
            stage, document = self.split(request.job)
            observation = self.observation(self._binding(stage), document)
            if (observation is None or request.episode != r.episode or
                    request.observation != canonical(observation) or request.owner in self.revoked or
                    request.owner != self._binding(stage).owner):
                del self.pending[identity]
                return self._event("DiscardObsoleteOrDuplicate", before, "discarded", request_id=identity)
            valid = not timeout and validate(stage, observation, value)
            normalized = False
            if valid:
                c = self._candidate()
                cr = c.records[request.job]
                cr.value, cr.stamp = deepcopy(value), request.observation
                cr.evidence_owner, cr.evidence_request = request.owner, identity
                cr.failed = False
                del c.pending[identity]
                c.revision += 1
                try:
                    c._reconcile()
                    normalized = True
                except ValueError:
                    pass
                if normalized:
                    self._install(c)
                    return self._event("ResolveAccepted", before, "committed", request_id=identity,
                                       proposal=value, validation=True, normalization=True)
            del self.pending[identity]
            r.failed = r.attempts == self.budget
            return self._event("Timeout" if timeout else "ResolveRejected", before, "rejected",
                               request_id=identity, proposal=value, validation=valid, normalization=normalized)

    def check_publication(self):
        with self.lock:
            ready = not self.suspended and not self.pending and all(self._usable(k) for k in self.active)
            if not ready:
                return {"revision": self.revision, "snapshot": self.snapshot(), "ok": False}
            global_ok = ready
            for document in self.documents:
                a, v = self.key("architecture", document), self.key("verification", document)
                if a in self.active and v in self.active:
                    global_ok &= self.records[a].value["id_type"] == self.records[v].value["id_type"]
            return {"revision": self.revision, "snapshot": self.snapshot(), "ok": bool(global_ok)}

    def publish(self, checked=None):
        with self.lock:
            before = self.snapshot()
            checked = self.check_publication() if checked is None else checked
            # Recompute even for caller-provided check objects; no forged success bit is trusted.
            current = self.check_publication()
            if (checked["revision"] != self.revision or not checked["ok"] or not current["ok"] or
                    checked["snapshot"] != current["snapshot"]):
                return self._event("Publish", before, "rejected")
            self.published = {"revision": self.revision, "snapshot": deepcopy(checked["snapshot"])}
            return self._event("Publish", before, "published")

    def observe(self):
        with self.lock:
            return self._event("OptionalObservationStep", self.snapshot(), "stutter")
