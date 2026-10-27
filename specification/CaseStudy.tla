------------------------- MODULE CaseStudy -------------------------
EXTENDS DocumentPolicy
\* Restricted behavioral sublanguage only. Full Python workflow is not encoded here.
VARIABLE state
Init == state = "open"
Next == \E e \in Events : state' = Reference(TRUE,state,e)[2]
TypeOK == state \in States
Spec == Init /\ [][Next]_state
=============================================================================
