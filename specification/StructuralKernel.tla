------------------------- MODULE StructuralKernel -------------------------
EXTENDS FiniteSets
CONSTANTS Keys, Targets, Id, Refs
ASSUME KernelConditions == /\ IsFiniteSet(Keys) /\ Id \in [Keys -> Targets]
       /\ \A x,y \in Keys : Id[x] = Id[y] => x=y
       /\ Refs \in [Keys -> SUBSET Keys]
Trace == [q \in Keys |-> Id[q]]
Skeleton == {Id[q] : q \in Keys}
Edges == [q \in Keys |-> {Trace[r] : r \in Refs[q]}]
Coverage == DOMAIN Trace = Keys
Unique == \A x,y \in Keys : Trace[x] = Trace[y] => x=y
ReferencesValid == \A q \in Keys : Edges[q] \subseteq Skeleton
=============================================================================
