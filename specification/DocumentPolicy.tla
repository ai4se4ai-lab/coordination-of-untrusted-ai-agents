------------------------- MODULE DocumentPolicy -------------------------
EXTENDS Naturals, Sequences
States == {"open", "archived"}
Events == {"read", "put", "archive"}
Outputs == {200,409} \X States
Inputs == States \X Events
Reference(h,d,e) ==
 IF e = "archive" THEN <<200,"archived">>
 ELSE IF h /\ d="archived" /\ e="put" THEN <<409,"archived">>
 ELSE <<200,d>>
ValidTable(h,t) == t \in [Inputs -> Outputs] /\
                    \A x \in Inputs : t[x] = Reference(h,x[1],x[2])
Relation(h,t) == t \in [Inputs -> Outputs] /\
                   \A d \in States, e \in Events : t[<<d,e>>] = Reference(h,d,e)
SoundComplete == \A h \in BOOLEAN, t \in [Inputs -> Outputs] : ValidTable(h,t) <=> Relation(h,t)
ArchiveAbsorbing == \A e \in Events : Reference(TRUE,"archived",e)[2] = "archived"
PutConflict == Reference(TRUE,"archived","put")[1] = 409
=============================================================================
