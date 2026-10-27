---- MODULE Model_stale_publication ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {}]
====
