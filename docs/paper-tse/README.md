# TSE manuscript

`main.tex` is the IEEE Transactions on Software Engineering version of the
paper (IEEEtran, `compsoc` journal mode). The earlier Springer version in
`docs/paper/` is kept unchanged because `experiments/analysis.py` and
`scripts/check_claims.py` regenerate and verify its marked regions.

Every evaluation number, table and plot in this manuscript is generated, never
typed by hand:

| Fragment in `generated/` | Source data |
|---|---|
| `tab-tlc.tex`, `tab-scenarios.tex`, `tab-assurance.tex` | `results/processed/document-service-v1/detailed-results.json` |
| `fig-ablation.tex`, `fig-cost.tex`, `tab-cost.tex` | `results/processed/tse/campaign.json` |
| `numbers.tex` (macros used in the text) | both of the above, plus `results/processed/tse/prefix-defect.json` |

`generated/provenance.json` records SHA-256 hashes of the inputs, the generator
and every fragment.

```text
python scripts/reproduce.py tse-campaign   # RQ1 ablation + RQ2 cost (about 15-30 min)
python scripts/reproduce.py tse-paper      # regenerate generated/*.tex
cd docs/paper-tse && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

`references.bib` is the verified bibliography of the earlier version.
`references-tse.bib` holds the references added for TSE; each DOI was checked
against Crossref. Entries without a DOI (arXiv, ICLR, NeurIPS) must be rechecked
before submission.
