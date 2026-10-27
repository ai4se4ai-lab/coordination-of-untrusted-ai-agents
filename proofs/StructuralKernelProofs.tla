------------------------- MODULE StructuralKernelProofs -------------------------
EXTENDS StructuralKernel, TLAPS
THEOREM CurrentCoverage == Coverage
BY KernelConditions, SMT DEF Coverage, Trace
THEOREM UniqueProducer == Unique
BY KernelConditions, SMT DEF Unique, Trace
THEOREM NoDanglingReference == ReferencesValid
BY KernelConditions, SMT DEF ReferencesValid, Edges, Trace, Skeleton
=============================================================================
