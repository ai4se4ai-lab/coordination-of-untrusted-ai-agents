---- MODULE Model_chain_k1 ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {} [] 2 = j -> {1}]
====
