"""
Pipeline: Wire all components together for synthetic data generation (v4.1).
"""

import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np

from .models import Branch, Entry, Soldier, Source
from .clerk_factory import ClerkFactory
from .situation_manager import SituationManager
from .vocabulary_injector import VocabularyInjector
from .source_generator import SourceGenerator
from .hierarchy_loader import HierarchyLoader
from .soldier_factory import SoldierFactory
from .renderer import Renderer
from .completeness_analyzer import CompletenessAnalyzer
from .difficulty_computer import DifficultyComputer
from .difficulty_rebalancer import DifficultyRebalancer


class Pipeline:
    """Main pipeline for synthetic data generation."""

    def __init__(
        self,
        style_spec_path: Path,
        themes_path: Path,
        vocabulary_path: Path,
        hierarchy_path: Path,
        random_seed: Optional[int] = None,
    ):
        self.rng = random.Random(random_seed)
        self.np_rng = np.random.default_rng(random_seed)
        self.seed = random_seed

        self.clerk_factory = ClerkFactory(
            style_spec_path=style_spec_path,
            random_seed=random_seed,
        )
        self.situation_manager = SituationManager(
            themes_path=themes_path,
            vocabulary_path=vocabulary_path,
            random_seed=random_seed,
        )
        self.vocabulary_injector = VocabularyInjector(
            vocabulary_path=vocabulary_path,
            random_seed=random_seed,
        )
        self.hierarchy_loader = HierarchyLoader(
            config_path=hierarchy_path,
        )
        self.soldier_factory = SoldierFactory(
            hierarchy=self.hierarchy_loader,
            rng=self.np_rng,
        )
        self.renderer = Renderer(
            hierarchy_loader=self.hierarchy_loader,
            random_seed=random_seed,
        )
        self.source_generator = SourceGenerator(
            clerk_factory=self.clerk_factory,
            situation_manager=self.situation_manager,
            random_seed=random_seed,
        )

        self.completeness_analyzer = CompletenessAnalyzer(self.hierarchy_loader)
        self.difficulty_computer = DifficultyComputer(self.completeness_analyzer)
        self.rebalancer = DifficultyRebalancer()

        self.soldiers: Dict[str, Soldier] = {}
        self.sources: Dict[str, Source] = {}
        self.entries: Dict[str, Entry] = {}
        self._entry_counter = 0

    def _generate_entry_id(self) -> str:
        self._entry_counter += 1
        return f"ENT{self._entry_counter:06d}"

    def generate(
        self,
        target_records: int = 10000,
        soldiers_count: Optional[int] = None,
    ) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Generate synthetic dataset records."""
        if soldiers_count is None:
            soldiers_count = max(1, target_records // 3)

        self._generate_soldiers(soldiers_count)

        total_entries = 0
        entries_by_soldier: Dict[str, List[Entry]] = {
            s.soldier_id: [] for s in self.soldiers.values()
        }

        while total_entries < target_records:
            source_size = self._entries_per_source()
            source_size = min(source_size, target_records - total_entries)
            if source_size <= 0:
                break

            temporal_anchor = self.rng.choice([1, 2, 3])
            source_soldiers = self._sample_soldiers_for_source(
                list(self.soldiers.values()),
                source_size,
                temporal_anchor,
            )
            if not source_soldiers:
                break

            states_for_source = [
                self._select_state_for_source(soldier, temporal_anchor)
                for soldier in source_soldiers
            ]
            home_unit = self._determine_home_unit(states_for_source)
            branch = self._branch_from_home_unit(home_unit) or states_for_source[0].branch

            source = self.source_generator.create_source(
                branch=branch,
                home_unit=home_unit,
                temporal_anchor=temporal_anchor,
            )
            self.sources[source.source_id] = source

            clerk = self.clerk_factory.get_clerk(source.clerk_id)
            situation = self.situation_manager.get_situation(source.situation_id)
            if not clerk or not situation:
                continue

            for soldier, state in zip(source_soldiers, states_for_source):
                entry_id = self._generate_entry_id()
                entry = self.renderer.render_entry(
                    entry_id=entry_id,
                    soldier=soldier,
                    state=state,
                    source=source,
                    clerk=clerk,
                    situation=situation,
                    vocabulary_injector=self.vocabulary_injector,
                )
                self.entries[entry.entry_id] = entry
                entries_by_soldier[soldier.soldier_id].append(entry)
                clerk.entry_count += 1

            total_entries += source_size

        for soldier in self.soldiers.values():
            soldier_entries = entries_by_soldier.get(soldier.soldier_id, [])
            self.difficulty_computer.compute_difficulty(soldier, soldier_entries)

        if self.rebalancer.needs_rebalancing(list(self.soldiers.values())):
            self.rebalancer.identify_adjustments(list(self.soldiers.values()))

        raw_records = self._build_raw_records()
        validation_records = self._build_validation_records()
        source_records = self._build_source_records()
        synthetic_records = self._build_synthetic_records()
        synthetic_soldiers = self._build_synthetic_soldiers()

        return (
            raw_records,
            validation_records,
            source_records,
            synthetic_records,
            synthetic_soldiers,
        )

    def _generate_soldiers(self, count: int) -> None:
        """Generate soldiers across branches."""
        for i in range(count):
            soldier = self.soldier_factory.create_soldier(f"S{i:04d}")
            self.soldiers[soldier.soldier_id] = soldier

    def _entries_per_source(self) -> int:
        """Sample entries per source from a truncated normal distribution."""
        count = int(self.rng.gauss(35, 15))
        return max(8, min(80, count))

    def _sample_soldiers_for_source(
        self,
        soldiers: List[Soldier],
        count: int,
        temporal_anchor: int,
    ) -> List[Soldier]:
        """Sample soldiers with unit concentration by Level-3."""
        if not soldiers:
            return []

        count = min(count, len(soldiers))
        primary = self.rng.choice(soldiers)
        primary_state = self._select_state_for_source(primary, temporal_anchor)
        primary_branch = primary_state.branch

        same_branch = [
            s for s in soldiers
            if self._select_state_for_source(s, temporal_anchor).branch == primary_branch
        ]

        result: List[Soldier] = [primary]
        chosen = {primary.soldier_id}
        while len(result) < count:
            pool = same_branch if self.rng.random() < 0.70 and same_branch else soldiers
            candidates = [s for s in pool if s.soldier_id not in chosen]
            if not candidates:
                candidates = [s for s in soldiers if s.soldier_id not in chosen]
            if not candidates:
                break
            pick = self.rng.choice(candidates)
            result.append(pick)
            chosen.add(pick.soldier_id)

        return result

    def _select_state_for_source(self, soldier: Soldier, temporal_anchor: int):
        """Select which state a source captures for a soldier."""
        if temporal_anchor <= len(soldier.states):
            return soldier.states[temporal_anchor - 1]
        return soldier.states[-1]

    def _determine_home_unit(self, states) -> str:
        """Determine the home unit for a source based on majority Level-3."""
        counts: Dict[str, int] = {}
        for state in states:
            home_unit = self._build_home_unit(state)
            counts[home_unit] = counts.get(home_unit, 0) + 1
        return max(counts, key=counts.get)

    def _build_home_unit(self, state) -> str:
        """Build a branch-prefixed Level-3 home unit string."""
        levels = self.hierarchy_loader.get_branch_levels(state.branch)
        level3 = levels[:3]
        path = "/".join(state.post_levels.get(lvl, "") for lvl in level3)
        return f"{state.branch.value}:{path}"

    def _branch_from_home_unit(self, home_unit: str) -> Optional[Branch]:
        if ":" not in home_unit:
            return None
        branch_str = home_unit.split(":", 1)[0]
        try:
            return Branch(branch_str)
        except ValueError:
            return None

    def _build_raw_records(self) -> List[Dict[str, Any]]:
        """Build raw records for export."""
        records = []
        for entry in self.entries.values():
            records.append({
                "source_id": entry.source_id,
                "soldier_id": entry.soldier_id,
                "raw_text": entry.raw_text,
            })
        return records

    def _build_validation_records(self) -> List[Dict[str, Any]]:
        """Build validation records for export."""
        records = []
        for soldier in self.soldiers.values():
            for state in soldier.states:
                records.append({
                    "soldier_id": soldier.soldier_id,
                    "state_id": state.state_id,
                    "state_order": state.state_order,
                    "branch": state.branch.value,
                    "post_path": state.post_path,
                    **state.post_levels,
                })
        return records

    def _build_source_records(self) -> List[Dict[str, Any]]:
        """Build sources records for export."""
        records = []
        for source in self.sources.values():
            records.append({
                "source_id": source.source_id,
                "clerk_id": source.clerk_id,
                "situation_id": source.situation_id,
                "quality_tier": source.quality_tier,
                "home_unit": source.home_unit,
                "temporal_anchor": source.temporal_anchor,
            })
        return records

    def _build_synthetic_records(self) -> List[Dict[str, Any]]:
        """Build per-record synthetic metadata for export."""
        records = []
        for entry in self.entries.values():
            records.append({
                "source_id": entry.source_id,
                "soldier_id": entry.soldier_id,
                "state_id": entry.state_id,
                "clerk_id": entry.clerk_id,
                "situation_id": entry.situation_id,
                "quality_tier": entry.quality_tier,
                "path_completeness": entry.path_completeness,
                "levels_provided": entry.levels_provided,
                "extraction_signals": entry.extraction_signals,
            })
        return records

    def _build_synthetic_soldiers(self) -> List[Dict[str, Any]]:
        """Build per-soldier synthetic generation metrics for export."""
        records = []
        for soldier in self.soldiers.values():
            records.append({
                "soldier_id": soldier.soldier_id,
                "gen_difficulty_tier": (
                    soldier.difficulty_tier.value
                    if soldier.difficulty_tier
                    else None
                ),
                "gen_complementarity_score": soldier.complementarity_score,
                "gen_structural_resolvability": soldier.structural_resolvability,
                "target_state_count": len(soldier.states),
            })
        return records

    def export_parquet(
        self,
        output_dir: Path,
        raw_records: List[Dict],
        validation_records: List[Dict],
        source_records: List[Dict],
        synthetic_records: Optional[List[Dict]] = None,
        synthetic_soldiers: Optional[List[Dict]] = None,
        gt_difficulty_records: Optional[List[Dict]] = None,
    ) -> None:
        """Export records to parquet files (with CSV fallback)."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for export")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        parquet_available = True
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            try:
                import fastparquet  # noqa: F401
            except ImportError:
                parquet_available = False
                print("Note: pyarrow not available, using CSV export")

        ext = ".parquet" if parquet_available else ".csv"

        if raw_records:
            raw_df = pd.DataFrame(raw_records)
            if parquet_available:
                raw_df.to_parquet(output_dir / "raw.parquet", index=False)
            else:
                raw_df.to_csv(output_dir / "raw.csv", index=False)
            print(f"Wrote {len(raw_df)} records to {output_dir}/raw{ext}")

        if validation_records:
            val_df = pd.DataFrame(validation_records)
            if parquet_available:
                val_df.to_parquet(output_dir / "validation.parquet", index=False)
            else:
                val_df.to_csv(output_dir / "validation.csv", index=False)
            print(f"Wrote {len(val_df)} records to {output_dir}/validation{ext}")

        if source_records:
            src_df = pd.DataFrame(source_records)
            if parquet_available:
                src_df.to_parquet(output_dir / "sources.parquet", index=False)
            else:
                src_df.to_csv(output_dir / "sources.csv", index=False)
            print(f"Wrote {len(src_df)} records to {output_dir}/sources{ext}")

        if synthetic_records:
            syn_df = pd.DataFrame(synthetic_records)
            if parquet_available:
                syn_df.to_parquet(output_dir / "synthetic_records.parquet", index=False)
            else:
                syn_df.to_csv(output_dir / "synthetic_records.csv", index=False)
            print(f"Wrote {len(syn_df)} records to {output_dir}/synthetic_records{ext}")

        if synthetic_soldiers:
            soldier_df = pd.DataFrame(synthetic_soldiers)
            if parquet_available:
                soldier_df.to_parquet(output_dir / "synthetic_soldiers.parquet", index=False)
            else:
                soldier_df.to_csv(output_dir / "synthetic_soldiers.csv", index=False)
            print(f"Wrote {len(soldier_df)} records to {output_dir}/synthetic_soldiers{ext}")

        if gt_difficulty_records:
            gt_df = pd.DataFrame(gt_difficulty_records)
            if parquet_available:
                gt_df.to_parquet(output_dir / "gt_difficulty.parquet", index=False)
            else:
                gt_df.to_csv(output_dir / "gt_difficulty.csv", index=False)
            print(f"Wrote {len(gt_df)} records to {output_dir}/gt_difficulty{ext}")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        entries_per_source: Dict[str, int] = {}
        for entry in self.entries.values():
            entries_per_source[entry.source_id] = entries_per_source.get(entry.source_id, 0) + 1

        difficulty_counts: Dict[str, int] = {}
        for soldier in self.soldiers.values():
            tier = soldier.difficulty_tier.value if soldier.difficulty_tier else "unknown"
            difficulty_counts[tier] = difficulty_counts.get(tier, 0) + 1

        return {
            "total_soldiers": len(self.soldiers),
            "total_sources": len(self.sources),
            "total_entries": len(self.entries),
            "avg_entries_per_source": (
                sum(entries_per_source.values()) / max(len(self.sources), 1)
            ),
            "difficulty_distribution": {
                k: v / max(len(self.soldiers), 1)
                for k, v in difficulty_counts.items()
            },
            "clerk_stats": self.clerk_factory.get_clerk_stats(),
            "situation_stats": self.situation_manager.get_assignment_stats(),
        }


def run_pipeline(
    output_dir: str = "data/synthetic",
    target_records: int = 10000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Convenience function to run the full pipeline."""
    style_spec = Path("docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml")
    themes_path = Path("config/synthetic/synthetic_themes.json")
    vocab_path = Path("config/synthetic/synthetic_vocabulary.json")
    hierarchy_path = Path("config/hierarchies/hierarchy_reference.json")

    pipeline = Pipeline(
        style_spec_path=style_spec,
        themes_path=themes_path,
        vocabulary_path=vocab_path,
        hierarchy_path=hierarchy_path,
        random_seed=random_seed,
    )

    raw_records, validation_records, source_records, synthetic_records, synthetic_soldiers = pipeline.generate(
        target_records=target_records,
    )

    gt_difficulty_records = None
    try:
        import pandas as pd
        from src.difficulty.ground_truth import compute_ground_truth_difficulty

        gt_df = compute_ground_truth_difficulty(
            validation_df=pd.DataFrame(validation_records),
            raw_df=pd.DataFrame(raw_records),
            hierarchy_reference=pipeline.hierarchy_loader.config,
            synthetic_records_df=pd.DataFrame(synthetic_records),
        )
        gt_difficulty_records = gt_df.to_dict("records")
    except ImportError:
        gt_difficulty_records = None

    pipeline.export_parquet(
        output_dir=Path(output_dir),
        raw_records=raw_records,
        validation_records=validation_records,
        source_records=source_records,
        synthetic_records=synthetic_records,
        synthetic_soldiers=synthetic_soldiers,
        gt_difficulty_records=gt_difficulty_records,
    )

    return pipeline.get_stats()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic data")
    parser.add_argument(
        "--output-dir", "-o",
        default="data/synthetic",
        help="Output directory for parquet files",
    )
    parser.add_argument(
        "--target-records", "-n",
        type=int,
        default=10000,
        help="Target number of raw entries",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args()

    print("Generating synthetic data...")
    print(f"  Output: {args.output_dir}")
    print(f"  Target records: {args.target_records}")
    print(f"  Seed: {args.seed}")

    stats = run_pipeline(
        output_dir=args.output_dir,
        target_records=args.target_records,
        random_seed=args.seed,
    )

    print("\n=== Generation Complete ===")
    print(f"Total soldiers: {stats['total_soldiers']}")
    print(f"Total sources: {stats['total_sources']}")
    print(f"Total entries: {stats['total_entries']}")
    print(f"Avg entries/source: {stats['avg_entries_per_source']:.1f}")
    print("\nDifficulty distribution:")
    for tier, ratio in stats["difficulty_distribution"].items():
        print(f"  {tier}: {ratio:.1%}")
