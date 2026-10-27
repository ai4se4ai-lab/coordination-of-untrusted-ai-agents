---- MODULE Model_publish_suspended ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {}]
====
