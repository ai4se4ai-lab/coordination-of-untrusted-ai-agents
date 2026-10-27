---- MODULE Model_no_recheck ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {}]
====
