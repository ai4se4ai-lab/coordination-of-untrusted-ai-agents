------------------------- MODULE ControllerSafety -------------------------
EXTENDS Naturals, TLAPS
\* A scoped admission lemma, not the inductive invariant of Core.tla.
CONSTANTS Proposals, Observations, Valid, Owner, Authorized
ASSUME Valid \in [Observations \X Proposals -> BOOLEAN]
VARIABLES current, dispatched, proposal, owner, active, accepted
Guard == /\ active /\ current = dispatched /\ owner = Owner /\ owner \in Authorized
         /\ current \in Observations /\ proposal \in Proposals
         /\ Valid[<<dispatched,proposal>>]
Commit == Guard /\ accepted' = <<current,proposal,owner>>
THEOREM CommitIsCurrentAuthorizedValid ==
 Commit => /\ accepted'[1] = dispatched /\ accepted'[3] \in Authorized
           /\ Valid[<<current,accepted'[2]>>]
BY SMT DEF Commit, Guard
=============================================================================
