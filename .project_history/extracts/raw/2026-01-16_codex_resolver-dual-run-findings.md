# Codex Session - Resolver Dual-Run Findings

Date: 2026-01-16
Scope: Resolver generation workflow (dual-run batching + reconciliation)

Findings:
- Hard case IDs can be dropped when batch-level `soldier_ids` (per soldier) do not align with per-record `target_texts`, which prevents the LLM from returning valid `hard_cases`.
- Dual-run mode currently runs the single-pass pattern discovery and then overwrites it, which doubles LLM cost and inflates token accounting.
- Hard case record lookup compares string IDs from the LLM to `records_df[soldier_id_col]` directly; if the dataframe column is numeric, reconciliation can see empty hard case records.

Notes:
- Captured in component documentation per README knowledge capture workflow.
