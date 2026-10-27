---- MODULE Model_revoked_authority ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {}]
====
