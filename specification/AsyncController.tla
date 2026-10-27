------------------------- MODULE AsyncController -------------------------
EXTENDS Core
VARIABLE s
vars == <<s>>
Init == s = Initial
EditField(field,j,v) ==
 /\ s.changes < MaxChanges
 /\ LET t == [s EXCEPT ![field][j] = v, !.rev = @+1, !.changes = @+1]
    IN s' = Reconcile(t,s)
EditSource == \E j \in Jobs, v \in Values : EditField("src",j,v)
UpdateContext == \E j \in Jobs, v \in Values : EditField("ctx",j,v)
Reconfigure == \E j \in Jobs :
       EditField("contract",j,1-s.contract[j]) \/ EditField("auth",j,~s.auth[j])
Lifecycle == \E j \in Jobs :
       EditField("exists",j,~s.exists[j]) \/ EditField("available",j,~s.available[j])
Dispatch(j) ==
 /\ j \in Dirty(s) /\ ~s.failed[j] /\ s.count[j] < K
 /\ ~\E r \in s.pending : r.job = j
 /\ LET r == [job |-> j, episode |-> s.episode[j], attempt |-> s.count[j]+1,
               obs |-> Obs(s,j), observedContract |-> s.contract[j], observedContext |-> s.ctx[j]]
    IN s' = [s EXCEPT !.count[j] = @+1, !.pending = @ \cup {r}, !.history = @ \cup {r}]
Current(r) == r \in s.pending /\ Active(s,r.job)
                /\ (s.auth[r.job] \/ IgnoreAuthority)
                /\ (~RecheckCurrent \/ (r.episode = s.episode[r.job] /\ r.obs = Obs(s,r.job)))
ResolveAccepted(r,v) ==
 /\ Current(r) /\ Valid(r.obs,v)
 /\ LET t == [s EXCEPT !.value[r.job] = v, !.stamp[r.job] = r.obs,
               !.evidence[r.job] = r, !.pending = @ \ {r}, !.failed[r.job] = FALSE,
               !.rev = @+1,
               !.commits = @ \cup {[dispatched |-> r.obs, current |-> Obs(s,r.job),
                                    authorized |-> s.auth[r.job],
                                    dispatchedContract |-> r.observedContract,
                                    currentContract |-> s.contract[r.job],
                                    dispatchedContext |-> r.observedContext,
                                    currentContext |-> s.ctx[r.job]]}]
    IN s' = Reconcile(t,s)
ResolveRejected(r) ==
 /\ Current(r)
 /\ s' = [s EXCEPT !.pending = @ \ {r}, !.failed[r.job] = (s.count[r.job] = K)]
Timeout(r) == ResolveRejected(r)
DiscardObsoleteOrDuplicate(r) ==
 /\ r \in s.history /\ ~Current(r)
 /\ s' = [s EXCEPT !.pending = @ \ {r}]
Publish ==
 /\ (IF IgnoreSuspension THEN Dirty(s) = {} /\ s.pending = {} ELSE Ready(s))
 /\ s' = [s EXCEPT !.pub = [clearQ |-> Q(s) = {}, clearDirty |-> Dirty(s) = {},
              clearPending |-> s.pending = {}, checked |-> IF StalePublication THEN 0 ELSE s.rev,
              installed |-> s.rev]]
BadReset == /\ ResetBudget /\ \E j \in Jobs : s.failed[j] /\
                    s' = [s EXCEPT !.count[j] = 0, !.failed[j] = FALSE]
OptionalObservationStep == UNCHANGED s
Next == EditSource \/ UpdateContext \/ Reconfigure \/ Lifecycle \/ Publish \/ BadReset
        \/ (\E j \in Jobs : Dispatch(j))
        \/ (\E r \in s.history :
              (\E v \in Values : ResolveAccepted(r,v)) \/ ResolveRejected(r) \/ Timeout(r)
              \/ DiscardObsoleteOrDuplicate(r))
        \/ OptionalObservationStep
Spec == Init /\ [][Next]_vars
Safety == Inv(s)
CurrentCommit == \A c \in s.commits : c.dispatched = c.current
ContractCommit == \A c \in s.commits : c.dispatchedContract = c.currentContract
ContextCommit == \A c \in s.commits : c.dispatchedContext = c.currentContext
AuthorityCommit == \A c \in s.commits : c.authorized
BudgetSafety == RequestBudget(s) /\ HistoryBudget(s)
SuspensionPublication == s.pub = None \/ s.pub.clearQ
RevisionPublication == s.pub = None \/ s.pub.checked = s.pub.installed
NoAcceptanceWitness == \A j \in Jobs : s.stamp[j] = None
NoExhaustionWitness == \A j \in Jobs : ~s.failed[j]
NoSuspensionWitness == Q(s) = {}
NoPublicationWitness == s.pub = None
NoContractChangeWitness == \A j \in Jobs : s.contract[j] = 0
DispatchAny == \E j \in Jobs : Dispatch(j)
SettleAny == \E r \in s.pending : ResolveRejected(r) \/ (\E v \in Values : ResolveAccepted(r,v))
\* Only frozen-input configurations (MaxChanges=0) use these finite liveness checks.
LiveSpec == Spec /\ WF_vars(DispatchAny) /\ WF_vars(SettleAny)
Terminal == s.pending = {} /\ \A j \in Dirty(s) : s.failed[j]
Termination == <>Terminal
=============================================================================
