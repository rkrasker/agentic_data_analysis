"""
Module 9: Reconciliation

Reconciles dual-run results and validates patterns against hard cases.
Produces final validated pattern set with confidence tiers.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Literal

import pandas as pd

from src.utils.llm import BaseLLMProvider, Message
from src.utils.llm.structured import extract_json_from_text

from .dual_run import DualRunResult, HardCase


logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PatternComparison:
    """Comparison of a pattern across dual runs."""
    pattern: str
    means: str = ""

    # Presence in runs
    in_forward: bool = False
    in_inverted: bool = False

    # Confidence from each run
    forward_confidence: Optional[str] = None
    inverted_confidence: Optional[str] = None

    # Reconciliation status
    status: Literal["robust", "validated", "order_dependent", "rejected"] = "order_dependent"
    final_confidence: Optional[str] = None

    # Hard case validation
    hard_case_pass: Optional[bool] = None
    hard_case_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "means": self.means,
            "in_forward": self.in_forward,
            "in_inverted": self.in_inverted,
            "status": self.status,
            "final_confidence": self.final_confidence,
            "hard_case_pass": self.hard_case_pass,
            "hard_case_notes": self.hard_case_notes,
        }


@dataclass
class HardCaseAnalysis:
    """Analysis of a hard case soldier."""
    soldier_id: str
    flagged_in: str  # "both", "forward_only", "inverted_only"
    reason: str
    notes: str = ""

    # Resolution analysis
    resolved_by_pattern: Optional[str] = None
    resolution_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "soldier_id": self.soldier_id,
            "flagged_in": self.flagged_in,
            "reason": self.reason,
            "notes": self.notes,
            "resolved_by_pattern": self.resolved_by_pattern,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class ReconciliationResult:
    """Result of reconciliation process."""
    component_id: str
    phase: str

    # Pattern classifications
    robust_patterns: List[PatternComparison] = field(default_factory=list)
    validated_patterns: List[PatternComparison] = field(default_factory=list)
    order_dependent_patterns: List[PatternComparison] = field(default_factory=list)
    rejected_patterns: List[PatternComparison] = field(default_factory=list)

    # Hard case analysis
    hard_case_analyses: List[HardCaseAnalysis] = field(default_factory=list)

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def final_patterns(self) -> List[Dict[str, Any]]:
        """
        Get final validated patterns for use in resolver.

        Includes robust and validated patterns; excludes order_dependent and rejected.
        """
        patterns = []

        for p in self.robust_patterns:
            patterns.append({
                "pattern": p.pattern,
                "means": p.means,
                "tier": p.final_confidence or "robust",
                "validation": "dual_run_robust",
            })

        for p in self.validated_patterns:
            patterns.append({
                "pattern": p.pattern,
                "means": p.means,
                "tier": p.final_confidence or "strong",
                "validation": "hard_case_validated",
            })

        return patterns

    @property
    def flagged_patterns(self) -> List[Dict[str, Any]]:
        """
        Get order-dependent patterns (not rejected, but flagged for review).
        """
        return [
            {
                "pattern": p.pattern,
                "means": p.means,
                "tier": "tentative",
                "validation": "order_dependent",
                "notes": f"Found in {'forward' if p.in_forward else 'inverted'} run only",
            }
            for p in self.order_dependent_patterns
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "phase": self.phase,
            "counts": {
                "robust": len(self.robust_patterns),
                "validated": len(self.validated_patterns),
                "order_dependent": len(self.order_dependent_patterns),
                "rejected": len(self.rejected_patterns),
            },
            "hard_cases_analyzed": len(self.hard_case_analyses),
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
            },
        }


# =============================================================================
# RECONCILIATION PROMPTS
# =============================================================================

RECONCILIATION_SYSTEM = """You are an expert at analyzing text patterns for military record classification.

Your task is to reconcile patterns discovered in two independent extraction runs and validate them against difficult cases.

Key principles:
1. Patterns found in BOTH runs are robust (order-independent)
2. Patterns found in only ONE run may be artifacts of processing order (drift)
3. Hard cases (ambiguous soldiers) are the true test of pattern quality
4. A pattern that fails on hard cases should be rejected or demoted

Be conservative: it's better to have fewer high-confidence patterns than many unreliable ones."""


def build_reconciliation_prompt(
    component_name: str,
    component_id: str,
    forward_patterns: List[Dict],
    inverted_patterns: List[Dict],
    hard_cases: List[HardCase],
    hard_case_records: Dict[str, List[str]],
) -> str:
    """Build prompt for reconciliation LLM call."""

    # Format patterns
    forward_str = "\n".join(
        f"  - {p.get('pattern', '')}: {p.get('means', '')} (confidence: {p.get('tier', 'unknown')})"
        for p in forward_patterns[:30]  # Limit to avoid token explosion
    )

    inverted_str = "\n".join(
        f"  - {p.get('pattern', '')}: {p.get('means', '')} (confidence: {p.get('tier', 'unknown')})"
        for p in inverted_patterns[:30]
    )

    # Format hard cases with records
    hard_case_strs = []
    for hc in hard_cases[:10]:  # Limit hard cases
        records = hard_case_records.get(hc.soldier_id, [])
        records_preview = "\n      ".join(records[:5])  # First 5 records
        hard_case_strs.append(
            f"  Soldier {hc.soldier_id} (flagged: {hc.flagged_in}, reason: {hc.reason}):\n"
            f"      {records_preview}"
        )

    hard_cases_str = "\n".join(hard_case_strs) if hard_case_strs else "  (no hard cases)"

    return f"""## Reconciliation Task

**Component:** {component_name} ({component_id})

### Patterns from Forward Run (batches processed A→B→C):
{forward_str or "  (none)"}

### Patterns from Inverted Run (batches processed C→B→A):
{inverted_str or "  (none)"}

### Hard Cases (soldiers flagged as difficult to classify):
{hard_cases_str}

## Instructions

1. **Compare patterns** between runs:
   - Identify patterns found in BOTH runs (robust)
   - Identify patterns found in only ONE run (order-dependent)

2. **Validate against hard cases**:
   - For each robust/order-dependent pattern, check if it correctly handles the hard cases
   - A pattern that fails on hard cases should be demoted or rejected

3. **Analyze hard case resolution**:
   - For hard cases flagged by only one run, identify what pattern from the OTHER run resolved it
   - This reveals pattern dependencies

Return JSON:
```json
{{
  "pattern_comparisons": [
    {{
      "pattern": "pattern text",
      "means": "what it indicates",
      "in_forward": true,
      "in_inverted": true,
      "status": "robust|validated|order_dependent|rejected",
      "final_confidence": "robust|strong|moderate|tentative",
      "hard_case_notes": "how it performed on hard cases"
    }}
  ],
  "hard_case_analyses": [
    {{
      "soldier_id": "S123",
      "resolution_notes": "Resolved by pattern X in inverted run",
      "resolved_by_pattern": "pattern text or null"
    }}
  ],
  "observations": "overall observations about pattern robustness"
}}
```"""


# =============================================================================
# RECONCILIATION LOGIC
# =============================================================================

class Reconciler:
    """
    Reconciles dual-run results and validates against hard cases.
    """

    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm

    def _compare_patterns_locally(
        self,
        forward_patterns: List[Dict],
        inverted_patterns: List[Dict],
    ) -> List[PatternComparison]:
        """
        Initial local comparison of patterns without LLM.

        Identifies which patterns appear in both runs vs one run.
        """
        # Index patterns by normalized key
        forward_index = {}
        for p in forward_patterns:
            key = p.get("pattern", "").lower().strip()
            if key:
                forward_index[key] = p

        inverted_index = {}
        for p in inverted_patterns:
            key = p.get("pattern", "").lower().strip()
            if key:
                inverted_index[key] = p

        # Find all unique patterns
        all_keys = set(forward_index.keys()) | set(inverted_index.keys())

        comparisons = []
        for key in all_keys:
            in_forward = key in forward_index
            in_inverted = key in inverted_index

            # Get pattern details
            if in_forward:
                p = forward_index[key]
            else:
                p = inverted_index[key]

            comparison = PatternComparison(
                pattern=p.get("pattern", ""),
                means=p.get("means", ""),
                in_forward=in_forward,
                in_inverted=in_inverted,
                forward_confidence=forward_index.get(key, {}).get("tier"),
                inverted_confidence=inverted_index.get(key, {}).get("tier"),
            )

            # Initial status based on presence
            if in_forward and in_inverted:
                comparison.status = "robust"
                # Average confidence or take higher
                comparison.final_confidence = comparison.forward_confidence or comparison.inverted_confidence
            else:
                comparison.status = "order_dependent"
                comparison.final_confidence = "tentative"

            comparisons.append(comparison)

        return comparisons

    def _get_hard_case_records(
        self,
        hard_cases: List[HardCase],
        records_df: pd.DataFrame,
        soldier_id_col: str = "soldier_id",
        text_col: str = "raw_text",
    ) -> Dict[str, List[str]]:
        """Get raw text records for hard case soldiers."""
        hard_case_ids = {hc.soldier_id for hc in hard_cases}

        result = {}
        for soldier_id in hard_case_ids:
            soldier_records = records_df[records_df[soldier_id_col] == soldier_id]
            result[soldier_id] = soldier_records[text_col].tolist()

        return result

    def reconcile(
        self,
        dual_run_result: DualRunResult,
        records_df: pd.DataFrame,
        component_name: str,
        soldier_id_col: str = "soldier_id",
        text_col: str = "raw_text",
    ) -> ReconciliationResult:
        """
        Reconcile dual-run results with LLM validation.

        Args:
            dual_run_result: Result from dual-run extraction
            records_df: DataFrame with all soldier records
            component_name: Human-readable component name
            soldier_id_col: Column name for soldier ID
            text_col: Column name for text

        Returns:
            ReconciliationResult with validated patterns
        """
        logger.info(f"Reconciling {dual_run_result.component_id} ({dual_run_result.phase})")

        # Local comparison first
        comparisons = self._compare_patterns_locally(
            dual_run_result.forward_result.accumulated_patterns,
            dual_run_result.inverted_result.accumulated_patterns,
        )

        robust_count = sum(1 for c in comparisons if c.status == "robust")
        order_dep_count = sum(1 for c in comparisons if c.status == "order_dependent")
        logger.info(f"  Local comparison: {robust_count} robust, {order_dep_count} order-dependent")

        # Get hard cases with agreement info
        hard_cases = dual_run_result.get_hard_cases_with_agreement()

        # If no hard cases or few patterns, skip LLM validation
        if not hard_cases or len(comparisons) == 0:
            logger.info("  Skipping LLM validation (no hard cases or patterns)")
            return self._build_result_without_llm(dual_run_result, comparisons, [])

        # Get records for hard cases
        hard_case_records = self._get_hard_case_records(
            hard_cases, records_df, soldier_id_col, text_col
        )

        # Build and run LLM reconciliation
        prompt = build_reconciliation_prompt(
            component_name=component_name,
            component_id=dual_run_result.component_id,
            forward_patterns=dual_run_result.forward_result.accumulated_patterns,
            inverted_patterns=dual_run_result.inverted_result.accumulated_patterns,
            hard_cases=hard_cases,
            hard_case_records=hard_case_records,
        )

        messages = [
            Message(role="system", content=RECONCILIATION_SYSTEM),
            Message(role="human", content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            result_json = extract_json_from_text(response.content)

            if result_json:
                return self._build_result_from_llm(
                    dual_run_result,
                    comparisons,
                    hard_cases,
                    result_json,
                    response.input_tokens,
                    response.output_tokens,
                )
            else:
                logger.warning("  LLM response did not contain valid JSON")
                return self._build_result_without_llm(dual_run_result, comparisons, hard_cases)

        except Exception as e:
            logger.error(f"  LLM reconciliation failed: {e}")
            return self._build_result_without_llm(dual_run_result, comparisons, hard_cases)

    def _build_result_without_llm(
        self,
        dual_run_result: DualRunResult,
        comparisons: List[PatternComparison],
        hard_cases: List[HardCase],
    ) -> ReconciliationResult:
        """Build result using only local comparison (no LLM validation)."""
        result = ReconciliationResult(
            component_id=dual_run_result.component_id,
            phase=dual_run_result.phase,
        )

        for c in comparisons:
            if c.status == "robust":
                result.robust_patterns.append(c)
            else:
                result.order_dependent_patterns.append(c)

        # Convert hard cases to analyses (without resolution info)
        for hc in hard_cases:
            result.hard_case_analyses.append(HardCaseAnalysis(
                soldier_id=hc.soldier_id,
                flagged_in=hc.flagged_in,
                reason=hc.reason,
                notes=hc.notes,
            ))

        return result

    def _build_result_from_llm(
        self,
        dual_run_result: DualRunResult,
        comparisons: List[PatternComparison],
        hard_cases: List[HardCase],
        llm_result: Dict,
        input_tokens: int,
        output_tokens: int,
    ) -> ReconciliationResult:
        """Build result incorporating LLM validation."""
        result = ReconciliationResult(
            component_id=dual_run_result.component_id,
            phase=dual_run_result.phase,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Index LLM results by pattern
        llm_comparisons = {}
        for pc in llm_result.get("pattern_comparisons", []):
            key = pc.get("pattern", "").lower().strip()
            if key:
                llm_comparisons[key] = pc

        # Update comparisons with LLM validation
        for c in comparisons:
            key = c.pattern.lower().strip()
            llm_pc = llm_comparisons.get(key, {})

            # Update status from LLM if provided
            if llm_pc.get("status"):
                c.status = llm_pc["status"]

            if llm_pc.get("final_confidence"):
                c.final_confidence = llm_pc["final_confidence"]

            if llm_pc.get("hard_case_notes"):
                c.hard_case_notes = llm_pc["hard_case_notes"]

            # Classify into result buckets
            if c.status == "robust":
                result.robust_patterns.append(c)
            elif c.status == "validated":
                result.validated_patterns.append(c)
            elif c.status == "rejected":
                result.rejected_patterns.append(c)
            else:
                result.order_dependent_patterns.append(c)

        # Process hard case analyses from LLM
        llm_hc_analyses = {
            hca.get("soldier_id"): hca
            for hca in llm_result.get("hard_case_analyses", [])
        }

        for hc in hard_cases:
            llm_hca = llm_hc_analyses.get(hc.soldier_id, {})

            result.hard_case_analyses.append(HardCaseAnalysis(
                soldier_id=hc.soldier_id,
                flagged_in=hc.flagged_in,
                reason=hc.reason,
                notes=hc.notes,
                resolved_by_pattern=llm_hca.get("resolved_by_pattern"),
                resolution_notes=llm_hca.get("resolution_notes", ""),
            ))

        logger.info(f"  Reconciliation complete: {len(result.robust_patterns)} robust, "
                   f"{len(result.validated_patterns)} validated, "
                   f"{len(result.order_dependent_patterns)} order-dependent, "
                   f"{len(result.rejected_patterns)} rejected")

        return result


def reconcile_patterns(
    dual_run_result: DualRunResult,
    records_df: pd.DataFrame,
    component_name: str,
    llm: BaseLLMProvider,
) -> ReconciliationResult:
    """
    Convenience function to reconcile dual-run results.

    Args:
        dual_run_result: Result from dual-run extraction
        records_df: DataFrame with soldier records
        component_name: Human-readable component name
        llm: LLM provider

    Returns:
        ReconciliationResult with validated patterns
    """
    reconciler = Reconciler(llm)
    return reconciler.reconcile(dual_run_result, records_df, component_name)
