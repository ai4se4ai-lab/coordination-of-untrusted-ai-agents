---- MODULE Model_no_cancel ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {}]
====
