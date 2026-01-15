# Thread Extract: Landing Zone + LLM Utils Placement

**Date:** 2026-01-14
**LLM:** Codex
**Session:** landing-zone-llm-utils
**Participants:** Eli, Codex

---

## Context

Set up a temporary landing area for reference materials, then promoted the useful LLM-related artifacts into the main codebase/docs with clearer placement.

---

## Key Actions

1. **Created landing_zone scaffold**
   - Added `landing_zone/README.md` with lifecycle guidance.
   - Added `landing_zone/archive/0000-00-00/.gitkeep` as a template.

2. **Promoted LLM utilities into src**
   - Moved `cost_tracker.py` → `src/utils/cost_tracker.py`.
   - Moved `gemini_helper.py` → `src/utils/gemini_helper.py`.
   - Added `src/utils/llm_client.py` as a minimal provider-agnostic interface.
   - Updated references in setup/cost docs.

3. **Moved reference docs into docs/**
   - `SETUP_GEMINI.md` → `docs/setup/SETUP_GEMINI.md`.
   - `COST_TRACKING_README.md` → `docs/components/llm/COST_TRACKING.md`.

---

## Decisions

- Landing zone is for short-term references; used items either get archived under `landing_zone/archive/YYYY-MM-DD/` or deleted after gist extraction.
- LLM-related utilities live under `src/utils/` until strategy implementations are added.

---

## Artifacts

- New/updated: `landing_zone/README.md`, `landing_zone/archive/0000-00-00/.gitkeep`
- New/updated: `src/utils/cost_tracker.py`, `src/utils/gemini_helper.py`, `src/utils/llm_client.py`
- Moved: `docs/setup/SETUP_GEMINI.md`, `docs/components/llm/COST_TRACKING.md`
