------------------------- MODULE DocumentPolicyProofs -------------------------
EXTENDS DocumentPolicy, TLAPS
THEOREM ValidatorEquivalence == SoundComplete
BY SMT DEF SoundComplete, ValidTable, Relation, Inputs, States, Events
THEOREM ArchivedRemainsArchived == ArchiveAbsorbing
BY SMT DEF ArchiveAbsorbing, Reference, Events
THEOREM ArchivedPutConflicts == PutConflict
BY SMT DEF PutConflict, Reference
=============================================================================
