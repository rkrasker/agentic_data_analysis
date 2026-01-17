# Thread Extract: Few-Shot Strategy Notes

Date: 2026-01-15
Source: Codex CLI session

Key excerpts:
- Few-shot should use curated soldier-level exemplars that mirror resolver workflow at consolidation time.
- Inputs per batch: raw text + hierarchy + small labeled exemplar set (5–15) matched to likely component(s) and collision rivals.
- Exemplars include raw records, extracted signals, final assignment, and short rationale.
- Selection should be stratified by ambiguity and include near-miss rivals.
- Assumes batches are grouped by likely component; otherwise use multi-component exemplars or a routing step.
- Maintain a small exemplar bank per component/collision; inject alongside resolvers or as fallback when resolver sections are sparse.
