------------------------- MODULE AtomicController -------------------------
EXTENDS Core
\* Independent atomic accepted-update interface. Transport is absent.
VARIABLE a
vars == <<a>>
Init == a = [Initial EXCEPT !.pending = {}, !.history = {}, !.commits = {}]
Attempt(j) == /\ j \in Dirty(a) /\ ~a.failed[j] /\ a.count[j] < K
              /\ a' = [a EXCEPT !.count[j] = @+1]
Accept(j,v) == /\ j \in Dirty(a) /\ a.auth[j] /\ a.count[j] > 0 /\ Valid(Obs(a,j),v)
              /\ LET t == [a EXCEPT !.value[j] = v, !.stamp[j] = Obs(a,j),
                                  !.failed[j] = FALSE, !.rev = @+1]
                 IN a' = Reconcile(t,a)
Fail(j) == /\ j \in Dirty(a) /\ a.count[j] > 0
           /\ a' = [a EXCEPT !.failed[j] = (a.count[j] = K)]
Edit(field,j,v) == /\ a.changes < MaxChanges
                   /\ LET t == [a EXCEPT ![field][j] = v, !.rev = @+1, !.changes = @+1]
                      IN a' = Reconcile(t,a)
Publish == /\ Q(a) = {} /\ Dirty(a) = {}
           /\ a' = [a EXCEPT !.pub = [clearQ |-> TRUE, clearDirty |-> TRUE,
                         clearPending |-> TRUE, checked |-> a.rev, installed |-> a.rev]]
Next == (\E j \in Jobs : Attempt(j) \/ Fail(j) \/ (\E v \in Values : Accept(j,v)))
        \/ (\E j \in Jobs, f \in {"src","ctx"}, v \in Values : Edit(f,j,v))
        \/ (\E j \in Jobs : Edit("contract",j,1-a.contract[j]) \/ Edit("auth",j,~a.auth[j])
                            \/ Edit("exists",j,~a.exists[j]) \/ Edit("available",j,~a.available[j]))
        \/ Publish
Spec == Init /\ [][Next]_vars
=============================================================================
