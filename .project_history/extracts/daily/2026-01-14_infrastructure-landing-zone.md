# Daily Reconciliation: Landing Zone and LLM Utilities Organization

**Date:** 2026-01-14
**Namespace:** infrastructure / landing-zone / llm-utils

---

## Summary

Established project infrastructure patterns for managing reference materials and organizing LLM-related utilities. Created a "landing zone" area for temporary references with explicit lifecycle management, and promoted LLM utilities from ad-hoc placement into structured `src/utils/` and `docs/` locations.

---

## What Changed

### Files Created

| File | Location |
|------|----------|
| `landing_zone/README.md` | Root |
| `landing_zone/archive/0000-00-00/.gitkeep` | Template structure |
| `src/utils/cost_tracker.py` | Promoted from root |
| `src/utils/gemini_helper.py` | Promoted from root |
| `src/utils/llm_client.py` | New provider-agnostic interface |

### Files Moved

| From | To |
|------|-----|
| `SETUP_GEMINI.md` | `docs/setup/SETUP_GEMINI.md` |
| `COST_TRACKING_README.md` | `docs/components/llm/COST_TRACKING.md` |

---

## Key Design Decisions

### 1. Landing Zone Pattern

Created `landing_zone/` as a staging area for reference materials with explicit lifecycle:
- **Purpose:** Temporary storage for PDFs, screenshots, research notes
- **Lifecycle:** Items either get archived under `archive/YYYY-MM-DD/` after extracting insights, or deleted if no longer needed
- **Not for:** Active code, documentation, or permanent references

This prevents root directory clutter while maintaining traceability.

### 2. LLM Utilities Placement

Promoted LLM-related code from root/ad-hoc locations into structured paths:
- **Utils in `src/utils/`** — Cost tracking, provider helpers, client interface
- **Docs in `docs/`** — Setup guides (`docs/setup/`), component docs (`docs/components/llm/`)
- **Rationale:** Utilities live in `src/utils/` until strategy implementations are added; then they may move to `src/strategies/llm/` or similar

### 3. Provider-Agnostic Interface

Added `llm_client.py` as a minimal abstraction over provider-specific helpers:
- Allows strategy code to avoid direct Gemini/OpenAI/Anthropic dependencies
- Current implementation wraps Gemini, but interface designed for multi-provider support
- Not a full abstraction layer yet — evolve as actual strategy needs emerge

---

## Impact on Other Components

| Component | Impact |
|-----------|--------|
| Strategy implementations | Will use `llm_client.py` interface rather than direct provider calls |
| Cost tracking | Now documented in `docs/components/llm/COST_TRACKING.md` |
| Setup process | Gemini setup guide now in `docs/setup/SETUP_GEMINI.md` |
| Root directory | Cleaner — LLM artifacts moved to appropriate locations |

---

## Infrastructure Patterns Established

1. **Landing zone lifecycle:** Temporary → Archive or Delete
2. **Utils placement:** `src/utils/` for cross-component code without a natural home
3. **Documentation hierarchy:** `docs/setup/` for setup guides, `docs/components/[name]/` for component-specific docs
4. **Provider abstraction:** Interface layer for LLM providers to support future multi-provider support

---

## Source

Raw extract: `.project_history/extracts/raw/2026-01-14_codex_landing-zone-llm-utils.md`
