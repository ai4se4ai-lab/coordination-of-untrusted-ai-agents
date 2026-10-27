------------------------------ MODULE Core ------------------------------
EXTENDS Naturals, FiniteSets, Sequences
CONSTANTS Jobs, Values, K, MaxChanges, Parent, None,
          CancelObsolete, RecheckCurrent, ResetBudget, IgnoreContract,
          IgnoreContext, IgnoreSuspension, IgnoreAuthority, StalePublication
ASSUME /\ Jobs = 1..Cardinality(Jobs)
       /\ Values # {} /\ K \in Nat \ {0} /\ MaxChanges \in Nat
       /\ Parent \in [Jobs -> SUBSET Jobs]
       /\ \A j \in Jobs : Parent[j] \subseteq 1..(j-1)
       /\ None \notin Values

RECURSIVE Usable(_, _)
Obs(t,j) == <<t.src[j], IF IgnoreContext THEN None ELSE t.ctx[j],
              IF IgnoreContract THEN None ELSE t.contract[j],
              t.auth[j], [p \in Parent[j] |-> t.value[p]]>>
Active(t,j) == /\ t.exists[j] /\ t.available[j]
               /\ (t.auth[j] \/ IgnoreAuthority)
               /\ \A p \in Parent[j] : Usable(t,p)
Usable(t,j) == Active(t,j) /\ t.stamp[j] = Obs(t,j)
Q(t) == {j \in Jobs : t.exists[j] /\ ~Active(t,j)}
Dirty(t) == {j \in Jobs : Active(t,j) /\ ~Usable(t,j)}
Valid(o,v) == v \in Values /\ v = o[1]
Reconcile(t,old) ==
 LET changed == {j \in Jobs : Active(t,j) /\
                     (~Active(old,j) \/ Obs(t,j) # old.signature[j])}
     ep == [j \in Jobs |-> IF j \in changed THEN t.nonce+j ELSE t.episode[j]]
     sg == [j \in Jobs |-> IF Active(t,j) THEN Obs(t,j) ELSE t.signature[j]]
     ct == [j \in Jobs |-> IF j \in changed THEN 0 ELSE t.count[j]]
     fl == [j \in Jobs |-> IF j \in changed THEN FALSE ELSE t.failed[j]]
     pend == {r \in t.pending : ~CancelObsolete \/
               (Active(t,r.job) /\ r.episode = ep[r.job] /\ r.obs = sg[r.job])}
 IN [t EXCEPT !.episode = ep, !.signature = sg, !.count = ct, !.failed = fl,
              !.pending = pend,
              !.nonce = IF changed = {} THEN t.nonce ELSE t.nonce+Cardinality(Jobs)]

Empty == [src |-> [j \in Jobs |-> CHOOSE v \in Values : TRUE],
          ctx |-> [j \in Jobs |-> CHOOSE v \in Values : TRUE],
          contract |-> [j \in Jobs |-> 0], auth |-> [j \in Jobs |-> TRUE],
          exists |-> [j \in Jobs |-> TRUE], available |-> [j \in Jobs |-> TRUE],
          value |-> [j \in Jobs |-> None], stamp |-> [j \in Jobs |-> None],
          evidence |-> [j \in Jobs |-> None], episode |-> [j \in Jobs |-> 0],
          signature |-> [j \in Jobs |-> None], count |-> [j \in Jobs |-> 0],
          failed |-> [j \in Jobs |-> FALSE], pending |-> {}, history |-> {},
          commits |-> {}, nonce |-> 0, rev |-> 0, pub |-> None, changes |-> 0]
Initial == Reconcile(Empty,Empty)
Ready(t) == Q(t) = {} /\ Dirty(t) = {} /\ t.pending = {}
TypeOK(t) == /\ t.src \in [Jobs -> Values] /\ t.ctx \in [Jobs -> Values]
             /\ t.contract \in [Jobs -> {0,1}]
             /\ t.auth \in [Jobs -> BOOLEAN] /\ t.exists \in [Jobs -> BOOLEAN]
             /\ t.available \in [Jobs -> BOOLEAN]
             /\ t.count \in [Jobs -> 0..K] /\ t.failed \in [Jobs -> BOOLEAN]
             /\ t.value \in [Jobs -> Values \cup {None}]
             /\ t.episode \in [Jobs -> Nat] /\ t.nonce \in Nat /\ t.rev \in Nat
RequestBudget(t) == \A j \in Jobs :
 Cardinality({r \in t.history : r.job = j /\ r.episode = t.episode[j]}) = t.count[j]
HistoryBudget(t) == \A r \in t.history :
 Cardinality({q \in t.history : q.job = r.job /\ q.episode = r.episode}) <= K
HistoryShape(t) ==
 /\ t.pending \subseteq t.history
 /\ \A r,q \in t.pending : r.job = q.job => r=q
 /\ \A r \in t.history :
     /\ r.job \in Jobs /\ r.episode \in 1..t.nonce /\ r.attempt \in 1..K
     /\ {q.attempt : q \in {q \in t.history : q.job=r.job /\ q.episode=r.episode}} =
        1..Cardinality({q \in t.history : q.job=r.job /\ q.episode=r.episode})
 /\ \A r,q \in t.history :
      (r.job=q.job /\ r.episode=q.episode /\ r.attempt=q.attempt) => r=q
Provenance(t) == \A j \in Jobs : t.stamp[j] # None =>
  /\ t.evidence[j] \in t.history /\ t.evidence[j].obs = t.stamp[j]
  /\ Valid(t.stamp[j],t.value[j])
CurrentValidity(t) == \A j \in Jobs : Usable(t,j) => Valid(Obs(t,j),t.value[j])
CommitSafety(t) == \A c \in t.commits :
 /\ c.dispatched = c.current /\ c.authorized
 /\ c.dispatchedContract = c.currentContract /\ c.dispatchedContext = c.currentContext
PublicationSafety(t) == t.pub = None \/
  (t.pub.clearQ /\ t.pub.clearDirty /\ t.pub.clearPending /\ t.pub.checked = t.pub.installed)
Inv(t) == TypeOK(t) /\ RequestBudget(t) /\ HistoryBudget(t) /\ HistoryShape(t) /\ Provenance(t)
          /\ CurrentValidity(t) /\ CommitSafety(t) /\ PublicationSafety(t)
=============================================================================
