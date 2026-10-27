---- MODULE Model_chain_terminal ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> IF j=1 THEN {} ELSE {1}]
====
