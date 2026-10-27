import json
import sys
from pathlib import Path
import unittest
from copy import deepcopy
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vgc.controller import Controller
from vgc.scheduler import repair
from vgc.types import Binding
from vgc.providers.scripted import valid_proposal
from vgc.validators import validate_table, table
from vgc.structure import allocate_resolve


class BoundaryTests(unittest.TestCase):
    def test_publication_is_total_at_each_partial_repair_boundary(self):
        c = Controller()
        for stage in ("requirements", "architecture", "implementation"):
            j = c.key(stage, "d1")
            u = c.dispatch(j)
            c.resolve(u, valid_proposal(c.pending[u]))
            self.assertFalse(c.check_publication()["ok"])
            self.assertEqual(c.publish(), "rejected")

    def test_required_views_and_structural_reads_cannot_be_omitted(self):
        c = Controller()
        before = c.snapshot()
        for bindings in ([], [Binding("implementation", 0, (), "implementation-worker")],
                         [replace(b, prerequisites=()) if b.stage == "implementation" else b for b in c.bindings]):
            self.assertEqual(c.reconfigure(bindings), "rejected")
            self.assertEqual(c.snapshot(), before)

    def test_deletion_recreation_does_not_reauthorize_old_request(self):
        c = Controller()
        j = c.key("requirements", "d1")
        old = c.dispatch(j)
        proposal = valid_proposal(c.pending[old])
        c.edit_source({})
        c.edit_source({"d1": {"strict": False}})
        new = c.dispatch(j)
        self.assertNotEqual(old, new)
        self.assertEqual(c.resolve(old, proposal), "discarded")
        self.assertIsNone(c.records[j].stamp)

    def test_duplicate_after_accept_cannot_overwrite(self):
        c = Controller()
        j = c.key("requirements", "d1")
        identity = c.dispatch(j)
        proposal = valid_proposal(c.pending[identity])
        self.assertEqual(c.resolve(identity, proposal), "committed")
        before = c.snapshot()
        self.assertEqual(c.resolve(identity, {}), "discarded")
        self.assertEqual(c.snapshot(), before)

    def test_proposal_and_input_aliases_do_not_modify_accepted_state(self):
        c = Controller()
        j = c.key("requirements", "d1")
        identity = c.dispatch(j)
        proposal = valid_proposal(c.pending[identity])
        c.resolve(identity, proposal)
        before = c.snapshot()
        proposal["clauses"].clear()
        self.assertEqual(c.snapshot(), before)

    def test_rejected_reconfiguration_rolls_back_everything(self):
        c = Controller()
        repair(c)
        before = c.snapshot()
        bindings = [replace(b, prerequisites=("verification",)) if b.stage == "architecture" else b for b in c.bindings]
        self.assertEqual(c.reconfigure(bindings), "rejected")
        self.assertEqual(c.snapshot(), before)

    def test_unavailable_context_blocks_publication_and_reactivates(self):
        c = Controller()
        repair(c)
        count = len(c.history)
        c.update_context(0, {}, available=False)
        self.assertIn(c.key("implementation", "d1"), c.suspended)
        self.assertEqual(c.publish(), "rejected")
        c.update_context(1, {}, available=True)
        self.assertTrue(repair(c))
        self.assertEqual(len(c.history), count)

    def test_zero_match_workflow_can_publish(self):
        c = Controller({})
        self.assertFalse(c.active)
        self.assertFalse(c.suspended)
        self.assertEqual(c.publish(), "published")

    def test_boolean_not_integer_and_malformed_rows_rejected(self):
        c = Controller({"d1": {"strict": True}})
        j = c.key("requirements", "d1")
        identity = c.dispatch(j)
        proposal = valid_proposal(c.pending[identity])
        proposal["strict"] = 1
        self.assertEqual(c.resolve(identity, proposal), "rejected")
        rows = table(True)
        rows[0]["status"] = True
        self.assertFalse(validate_table(True, rows))

    def test_kernel_namespace_encoding_and_missing_reference(self):
        keys = [("a:b", "c"), ("a", "b:c")]
        targets, _ = allocate_resolve(keys, {})
        self.assertEqual(len(set(targets.values())), 2)
        with self.assertRaises(ValueError):
            allocate_resolve(keys, {keys[0]: [("missing", "key")]})

    def test_forged_publication_check_cannot_install(self):
        c = Controller()
        forged = {"revision": c.revision, "snapshot": c.snapshot(), "ok": True}
        self.assertEqual(c.publish(forged), "rejected")

    def test_durable_counter_not_claimed(self):
        c = Controller()
        j = c.key("requirements", "d1")
        for _ in range(2):
            c.resolve(c.dispatch(j), timeout=True)
        c.edit_source(deepcopy(c.documents))
        self.assertIsNone(c.dispatch(j))
        self.assertEqual(len(c.history), 2)


if __name__ == "__main__":
    unittest.main()
