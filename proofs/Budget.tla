------------------------------ MODULE Budget ------------------------------
EXTENDS Naturals, TLAPS
CONSTANT K
ASSUME BudgetType == K \in Nat
VARIABLE count
Init == count = 0
Dispatch == count < K /\ count' = count+1
Other == UNCHANGED count
Inv == count \in Nat /\ count <= K
THEOREM InitialBound == Init => Inv
BY BudgetType, SMT DEF Init, Inv
THEOREM DispatchBound == Inv /\ Dispatch => Inv'
BY BudgetType, SMT DEF Inv, Dispatch
THEOREM OtherBound == Inv /\ Other => Inv'
BY SMT DEF Inv, Other
\* This isolated counter lemma is not the history/episode theorem for Core.
=============================================================================
