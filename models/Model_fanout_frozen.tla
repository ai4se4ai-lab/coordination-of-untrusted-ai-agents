---- MODULE Model_fanout_frozen ----
EXTENDS AsyncController
ModelParent == [j \in Jobs |-> CASE 1 = j -> {} [] 2 = j -> {1} [] 3 = j -> {1}]
====
