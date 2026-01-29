"""
Module 8: Dual-Run Orchestrator

Orchestrates dual-run stateful extraction per ADR-002.
Runs extraction twice with inverted batch order to expose drift
and collect hard cases for reconciliation.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Literal

import pandas as pd

from src.utils.llm import BaseLLMProvider, TokenBatch, TokenBatcher, TokenBatchConfig


logger = logging.getLogger(__name__)


@dataclass
class HardCase:
    """A soldier flagged as difficult to disambiguate."""
    soldier_id: str
    layer: str  # "collision_position" | "complementarity" | "structural_ambiguity" | "unknown"
    reason: str
    notes: str = ""
    flagged_in: str = ""  # "forward", "inverted", or "both"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "soldier_id": self.soldier_id,
            "layer": self.layer,
            "reason": self.reason,
            "notes": self.notes,
            "flagged_in": self.flagged_in,
        }


def parse_hard_cases(response: Dict[str, Any], phase_name: str) -> List[HardCase]:
    """Parse hard cases from an LLM response."""
    hard_cases = []
    for hc in response.get("hard_cases", []):
        layer = hc.get("layer") or "unknown"
        if layer == "unknown":
            logger.warning("Hard case missing layer field in %s; defaulting to 'unknown'", phase_name)
        hard_cases.append(HardCase(
            soldier_id=hc.get("soldier_id", ""),
            layer=layer,
            reason=hc.get("reason", ""),
            notes=hc.get("notes", ""),
        ))
    return hard_cases


@dataclass
class BatchExtractionResult:
    """Result from a single batch extraction."""
    batch_id: str
    patterns: List[Dict[str, Any]]
    hard_cases: List[HardCase]
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: str = ""


@dataclass
class RunResult:
    """Result from a single extraction run (forward or inverted)."""
    run_direction: Literal["forward", "inverted"]
    batch_results: List[BatchExtractionResult]
    accumulated_patterns: List[Dict[str, Any]]
    all_hard_cases: List[HardCase]

    @property
    def total_input_tokens(self) -> int:
        return sum(b.input_tokens for b in self.batch_results)

    @property
    def total_output_tokens(self) -> int:
        return sum(b.output_tokens for b in self.batch_results)

    @property
    def hard_case_ids(self) -> Set[str]:
        return {hc.soldier_id for hc in self.all_hard_cases}


@dataclass
class DualRunResult:
    """Combined result from forward and inverted extraction runs."""
    component_id: str
    phase: str  # "patterns", "vocabulary", "differentiators"

    forward_result: RunResult
    inverted_result: RunResult

    @property
    def all_hard_case_ids(self) -> Set[str]:
        """All soldier IDs flagged as hard cases in either run."""
        return self.forward_result.hard_case_ids | self.inverted_result.hard_case_ids

    @property
    def hard_case_agreement(self) -> Dict[str, str]:
        """
        Classify each hard case by which run(s) flagged it.

        Returns:
            Dict mapping soldier_id -> "both" | "forward_only" | "inverted_only"
        """
        forward_ids = self.forward_result.hard_case_ids
        inverted_ids = self.inverted_result.hard_case_ids

        agreement = {}
        for sid in self.all_hard_case_ids:
            if sid in forward_ids and sid in inverted_ids:
                agreement[sid] = "both"
            elif sid in forward_ids:
                agreement[sid] = "forward_only"
            else:
                agreement[sid] = "inverted_only"

        return agreement

    @property
    def total_input_tokens(self) -> int:
        return self.forward_result.total_input_tokens + self.inverted_result.total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self.forward_result.total_output_tokens + self.inverted_result.total_output_tokens

    def get_hard_cases_with_agreement(self) -> List[HardCase]:
        """Get all hard cases with flagged_in set to agreement status."""
        agreement = self.hard_case_agreement
        result = []

        # Collect from forward run
        for hc in self.forward_result.all_hard_cases:
            hc_copy = HardCase(
                soldier_id=hc.soldier_id,
                layer=hc.layer,
                reason=hc.reason,
                notes=hc.notes,
                flagged_in=agreement.get(hc.soldier_id, "forward_only"),
            )
            result.append(hc_copy)

        # Add any from inverted that weren't in forward
        forward_ids = self.forward_result.hard_case_ids
        for hc in self.inverted_result.all_hard_cases:
            if hc.soldier_id not in forward_ids:
                hc_copy = HardCase(
                    soldier_id=hc.soldier_id,
                    layer=hc.layer,
                    reason=hc.reason,
                    notes=hc.notes,
                    flagged_in="inverted_only",
                )
                result.append(hc_copy)

        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "phase": self.phase,
            "forward_patterns_count": len(self.forward_result.accumulated_patterns),
            "inverted_patterns_count": len(self.inverted_result.accumulated_patterns),
            "hard_cases_total": len(self.all_hard_case_ids),
            "hard_cases_both_runs": sum(1 for v in self.hard_case_agreement.values() if v == "both"),
            "hard_cases_forward_only": sum(1 for v in self.hard_case_agreement.values() if v == "forward_only"),
            "hard_cases_inverted_only": sum(1 for v in self.hard_case_agreement.values() if v == "inverted_only"),
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
            },
        }


@dataclass
class StatefulAccumulator:
    """
    Accumulator for stateful extraction across batches.

    Carries context from previous batches to inform subsequent extraction.
    """
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    vocabulary: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)

    def add_patterns(self, new_patterns: List[Dict[str, Any]]):
        """Add patterns, deduplicating by pattern text."""
        existing = {p.get("pattern", "").lower() for p in self.patterns}
        for p in new_patterns:
            key = p.get("pattern", "").lower()
            if key and key not in existing:
                self.patterns.append(p)
                existing.add(key)

    def add_vocabulary(self, new_vocab: List[str]):
        """Add vocabulary terms, deduplicating."""
        existing = {v.lower() for v in self.vocabulary}
        for v in new_vocab:
            if v.lower() not in existing:
                self.vocabulary.append(v)
                existing.add(v.lower())

    def add_observation(self, observation: str):
        """Add an observation from batch processing."""
        if observation:
            self.observations.append(observation)

    def to_context_string(self) -> str:
        """
        Generate context string to pass to subsequent batches.

        This provides the LLM with knowledge from previous batches.
        """
        parts = []

        if self.patterns:
            pattern_strs = [p.get("pattern", "") for p in self.patterns[:20]]  # Limit to avoid token explosion
            parts.append(f"Previously discovered patterns: {', '.join(pattern_strs)}")

        if self.vocabulary:
            vocab_sample = self.vocabulary[:30]
            parts.append(f"Previously identified vocabulary: {', '.join(vocab_sample)}")

        if self.observations:
            recent = self.observations[-3:]  # Last 3 observations
            parts.append(f"Previous observations: {'; '.join(recent)}")

        return "\n".join(parts) if parts else ""

    def clone(self) -> "StatefulAccumulator":
        """Create a deep copy."""
        return StatefulAccumulator(
            patterns=list(self.patterns),
            vocabulary=list(self.vocabulary),
            observations=list(self.observations),
        )


class DualRunOrchestrator:
    """
    Orchestrates dual-run extraction for a single phase.

    Runs extraction twice with inverted batch order to detect
    order-dependent patterns and collect hard cases.
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        extraction_fn: callable,
        token_budget: int = 8000,
    ):
        """
        Initialize orchestrator.

        Args:
            llm: LLM provider for extraction
            extraction_fn: Function to call for each batch extraction.
                Signature: (batch: TokenBatch, accumulator: StatefulAccumulator, llm: BaseLLMProvider)
                           -> BatchExtractionResult
            token_budget: Token budget per batch
        """
        self.llm = llm
        self.extraction_fn = extraction_fn
        self.token_budget = token_budget

    def run_single_pass(
        self,
        batches: List[TokenBatch],
        direction: Literal["forward", "inverted"],
    ) -> RunResult:
        """
        Run a single extraction pass over batches.

        Args:
            batches: List of token batches
            direction: "forward" or "inverted" order

        Returns:
            RunResult with accumulated patterns and hard cases
        """
        # Apply ordering
        if direction == "inverted":
            ordered_batches = list(reversed(batches))
        else:
            ordered_batches = batches

        logger.info(f"  Running {direction} pass over {len(ordered_batches)} batches")

        accumulator = StatefulAccumulator()
        batch_results = []
        all_hard_cases = []

        for i, batch in enumerate(ordered_batches):
            logger.debug(f"    Batch {i+1}/{len(ordered_batches)}: {batch.batch_id}")

            try:
                result = self.extraction_fn(batch, accumulator, self.llm)

                # Update accumulator with results
                accumulator.add_patterns(result.patterns)

                # Collect hard cases
                for hc in result.hard_cases:
                    hc.flagged_in = direction
                all_hard_cases.extend(result.hard_cases)

                batch_results.append(result)

            except Exception as e:
                logger.error(f"    Batch {batch.batch_id} failed: {e}")
                # Create empty result for failed batch
                batch_results.append(BatchExtractionResult(
                    batch_id=batch.batch_id,
                    patterns=[],
                    hard_cases=[],
                    raw_response=f"Error: {str(e)}",
                ))

        return RunResult(
            run_direction=direction,
            batch_results=batch_results,
            accumulated_patterns=accumulator.patterns,
            all_hard_cases=all_hard_cases,
        )

    def run_dual(
        self,
        component_id: str,
        records_df: pd.DataFrame,
        phase: str,
        soldier_id_col: str = "soldier_id",
        text_col: str = "raw_text",
    ) -> DualRunResult:
        """
        Run dual extraction (forward + inverted) for a component.

        Args:
            component_id: Component being processed
            records_df: DataFrame with soldier records
            phase: Phase name for logging
            soldier_id_col: Column name for soldier ID
            text_col: Column name for text

        Returns:
            DualRunResult with both runs' results
        """
        logger.info(f"Running dual extraction for {component_id} ({phase})")

        # Create batches
        batcher = TokenBatcher(TokenBatchConfig(
            token_budget=self.token_budget,
            batch_id_prefix=f"{component_id}_{phase}",
        ))

        batches = batcher.create_batches(
            records_df,
            soldier_id_col=soldier_id_col,
            text_col=text_col,
        )

        if not batches:
            logger.warning(f"  No batches created for {component_id}")
            empty_run = RunResult(
                run_direction="forward",
                batch_results=[],
                accumulated_patterns=[],
                all_hard_cases=[],
            )
            return DualRunResult(
                component_id=component_id,
                phase=phase,
                forward_result=empty_run,
                inverted_result=RunResult(
                    run_direction="inverted",
                    batch_results=[],
                    accumulated_patterns=[],
                    all_hard_cases=[],
                ),
            )

        summary = batcher.get_batch_summary(batches)
        logger.info(f"  Created {summary['batch_count']} batches, "
                   f"~{summary['total_tokens']} tokens total")

        # Run forward pass
        forward_result = self.run_single_pass(batches, "forward")
        logger.info(f"  Forward: {len(forward_result.accumulated_patterns)} patterns, "
                   f"{len(forward_result.all_hard_cases)} hard cases")

        # Run inverted pass
        inverted_result = self.run_single_pass(batches, "inverted")
        logger.info(f"  Inverted: {len(inverted_result.accumulated_patterns)} patterns, "
                   f"{len(inverted_result.all_hard_cases)} hard cases")

        result = DualRunResult(
            component_id=component_id,
            phase=phase,
            forward_result=forward_result,
            inverted_result=inverted_result,
        )

        # Log agreement summary
        agreement = result.hard_case_agreement
        both = sum(1 for v in agreement.values() if v == "both")
        forward_only = sum(1 for v in agreement.values() if v == "forward_only")
        inverted_only = sum(1 for v in agreement.values() if v == "inverted_only")
        logger.info(f"  Hard case agreement: {both} both, "
                   f"{forward_only} forward-only, {inverted_only} inverted-only")

        return result


def run_dual_extraction(
    component_id: str,
    records_df: pd.DataFrame,
    llm: BaseLLMProvider,
    extraction_fn: callable,
    phase: str = "patterns",
    token_budget: int = 8000,
) -> DualRunResult:
    """
    Convenience function to run dual extraction.

    Args:
        component_id: Component being processed
        records_df: DataFrame with soldier records
        llm: LLM provider
        extraction_fn: Batch extraction function
        phase: Phase name
        token_budget: Token budget per batch

    Returns:
        DualRunResult with both runs' results
    """
    orchestrator = DualRunOrchestrator(
        llm=llm,
        extraction_fn=extraction_fn,
        token_budget=token_budget,
    )

    return orchestrator.run_dual(
        component_id=component_id,
        records_df=records_df,
        phase=phase,
    )
