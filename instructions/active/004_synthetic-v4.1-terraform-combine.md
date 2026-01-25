# 004: Synthetic Data v4.1 - Terraform Combine Implementation

**Status:** Ready for execution
**Created:** 2026-01-25
**Updated:** 2026-01-25 (v4.1 difficulty framework)
**Model:** Sonnet, thinking on
**Component:** src/synthetic/, config/

---

## Objective

Implement the v4.1 synthetic data generation system based on ADR-007 (domain decontamination) and ADR-006 (three-layer difficulty model). This replaces the WWII military domain with a fictional interstellar setting (Terraform Combine) and adds explicit difficulty tracking at multiple levels.

**This is a rewrite, not a refactor.** The logic patterns transfer from v3, but the domain, vocabulary, hierarchy structures, and difficulty model are all new.

---

## Context

### Why This Change

**ADR-007 (Domain Decontamination):** LLM testing revealed the model was resolving unit assignments using pretraining knowledge rather than disambiguation signals in our data. A fictional domain gives clean attribution.

**ADR-006 (Difficulty Model):** Analysis revealed that **record quality ≠ state resolution difficulty**. A pristine record in a collision zone may be harder to resolve than degraded records that are complementary. The three-layer model separates extraction difficulty (Layer 1) from aggregation difficulty (Layer 2) from structural inference (Layer 3).

### What the ADRs Decided

**From ADR-007:**
1. **Domain decontamination**: Replace WWII military with "Terraform Combine"
2. **Explicit states**: `state_id` in all schemas; soldiers have 1-3 states
3. **Source-anchored states**: Each source captures one state per soldier
4. **Familiarity gradient**: Clerks abbreviate for home unit, spell out foreign units
5. **Heterogeneous branches**: 4 branches with different hierarchy depths (3-5 levels)
6. **Cross-branch transfers**: 15% of transfers cross branch boundaries

**From ADR-006:**
1. **Three-layer difficulty**: Extraction (L1), Aggregation (L2), Structural (L3)
2. **Collision zone tracking**: Tag posts that share designators with other posts
3. **Record completeness tracking**: Track which path levels each record provides
4. **Soldier-level difficulty**: Compute difficulty from all three layers
5. **Difficulty-aware generation**: Controls to hit target difficulty distributions

### Reference Documents

- **ADR-007**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **ADR-006**: `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **Style spec**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Design doc**: `docs/components/synthetic_data_generation/CURRENT.md`

---

## Scope

### In Scope (This Instruction)

| File | Change |
|------|--------|
| `config/hierarchies/hierarchy_reference.json` | **Full rewrite** - Terraform Combine branches + collision index |
| `config/synthetic/synthetic_vocabulary.json` | **Full rewrite** - New situational/clutter/confounder terms |
| `config/synthetic/synthetic_themes.json` | **Full rewrite** - Branch-based themes |
| `src/synthetic/models.py` | **Significant update** - State model, difficulty fields, new enums |
| `src/synthetic/hierarchy_loader.py` | **Update** - Support variable-depth + collision zone queries |
| `src/synthetic/soldier_factory.py` | **Significant update** - State generation, collision zone tagging |
| `src/synthetic/source_generator.py` | **Update** - Add home_unit, temporal_anchor |
| `src/synthetic/renderer.py` | **Significant update** - Familiarity-aware rendering + completeness tracking |
| `src/synthetic/clerk_factory.py` | **Update** - New archetype contexts |
| `src/synthetic/situation_manager.py` | **Update** - New situations |
| `src/synthetic/vocabulary_injector.py` | **Update** - Work with new vocabulary structure |
| `src/synthetic/transfer_manager.py` | **Update** - Cross-branch transfers, state model |
| `src/synthetic/completeness_analyzer.py` | **NEW** - Analyze record path coverage |
| `src/synthetic/difficulty_computer.py` | **NEW** - Compute soldier-level difficulty |
| `src/synthetic/difficulty_rebalancer.py` | **NEW** - Adjust generation to hit targets |
| `src/synthetic/pipeline.py` | **Update** - Wire state assignment + difficulty computation |

### Out of Scope (Future Work)

- Creating `seed_set_v4.json` (hand-crafted examples)
- Running the generation pipeline
- Updating preprocessing to handle new domain
- Updating evaluation metrics
- Any changes to resolver or strategy code

---

## The Three-Layer Difficulty Model

### Critical Insight

**Record quality (Layer 1) ≠ State resolution difficulty**

| Scenario | Record Quality | Resolution Difficulty |
|----------|---------------|-----------------------|
| Pristine record saying "3rd Squadron" in collision zone | High (Tier 1) | **Hard** (ambiguous post) |
| Degraded records that are complementary | Low (Tier 4-5) | **Easy** (jointly unique) |

### The Three Layers

| Layer | Question | Measured By | Where Computed |
|-------|----------|-------------|----------------|
| **1. Extraction** | Can we parse this record? | `quality_tier` (1-5) | Source level |
| **2. Aggregation** | Do records jointly resolve? | `complementarity_score` | Soldier level |
| **3. Structural** | Do constraints disambiguate? | `structural_resolvability` | Soldier level |

### Difficulty Tier Computation

```
EASY if:
  - Any record provides complete path (L1 sufficient), OR
  - Records are complementary and cover all segments (L2 sufficient), OR
  - Structural constraints resolve ambiguity (L3 sufficient)

MODERATE if:
  - Partial coverage but outside collision zone, OR
  - In collision zone but complementary records narrow it

HARD if:
  - In collision zone AND records are redundant, OR
  - Cross-branch transfer with ambiguous designators

EXTREME if:
  - Multiple states with cross-branch collision AND redundant records AND no structural resolution
```

### Target Difficulty Distribution

| Tier | Target | Generation Controls |
|------|--------|---------------------|
| Easy | 50% | Force complementary records, non-collision posts |
| Moderate | 30% | Allow some collision, ensure structural signals |
| Hard | 15% | Force collision zone + redundant records |
| Extreme | 5% | Cross-branch collision + minimal signals |

---

## The Terraform Combine Domain

### Branch Structures

| Branch | Abbreviation | Depth | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
|--------|--------------|-------|---------|---------|---------|---------|---------|
| Colonial Administration | CA | 4 | Sector | Colony | District | Settlement | — |
| Defense Command | DC | 5 | Sector | Fleet | Squadron | Wing | Element |
| Expeditionary Corps | EC | 3 | Sector | Expedition | Team | — | — |
| Resource Directorate | RD | 4 | Sector | Operation | Facility | Crew | — |

### Collision Design (Critical)

Designators are shared across branches to create ambiguity. The parser cannot rely on designator alone.

**Shared designators:**
- Numbers: 1-12 appear in multiple branches at multiple levels
- Letters: A-F appear as Element, Wing, Team, Crew designators
- Names: "Kestrel", "Amber", "Verdant", "Horizon" appear in multiple branches

**Example ambiguity:** Record saying `MARTINEZ SPEC3 7 ALPHA 3` is ambiguous:
- Fleet 7, Squadron Alpha, Wing 3 (Defense Command)?
- Facility 7, Crew Alpha, unknown (Resource Directorate)?
- District 7, Settlement Alpha... (Colonial Administration)?

### Collision Severity Levels

| Severity | Description | Example |
|----------|-------------|---------|
| **none** | Path is globally unique | Colony Waystation (Waystation is CA-only) |
| **low** | Collision only if 2+ levels omitted | Fleet Talon, 3rd Squadron (Talon is DC-only) |
| **medium** | Collision if 1+ levels omitted | Fleet Kestrel, 3rd Squadron (Kestrel shared) |
| **high** | Collision at most partial specs | Fleet 7, Squadron A (7 and A appear everywhere) |
| **cross_branch** | Designator collides across branches | Kestrel as Fleet vs Colony vs Expedition |

---

## Implementation Tasks

### Phase 1: Config Files

#### Task 1.1: hierarchy_reference.json

Rewrite to define Terraform Combine structure **with collision index**.

```json
{
  "meta": {
    "version": "4.1.0",
    "setting": "terraform_combine",
    "description": "Fictional interstellar hierarchy for methodological validation"
  },
  "branches": {
    "colonial_administration": {
      "branch_id": "colonial_administration",
      "abbreviation": "CA",
      "depth": 4,
      "levels": ["sector", "colony", "district", "settlement"],
      "level_config": {
        "sector": {"designator_style": "greek_letter", "values": ["Alpha", "Beta", "Gamma", "Delta"]},
        "colony": {"designator_style": "name", "values": ["Verdant", "Amber", "Kestrel", "Thornmark", "Waystation"]},
        "district": {"designator_style": "number", "values": ["1", "2", "3", "4", "5", "6", "7", "8"]},
        "settlement": {"designator_style": "name", "values": ["Haven", "Prospect", "Landfall", "Waypoint"]}
      },
      "unique_identifiers": ["Colony", "District", "Settlement"]
    }
    // Similar for defense_command, expeditionary_corps, resource_directorate
  },
  "collision_index": {
    "numbers": {
      "7": ["DC.fleet", "CA.district", "RD.facility", "EC.team"],
      "3": ["DC.squadron", "DC.wing", "CA.district", "RD.facility", "EC.team"],
      "1": ["DC.squadron", "DC.element", "CA.district", "RD.facility", "EC.team"]
    },
    "letters": {
      "A": ["DC.element", "DC.wing", "RD.crew", "EC.team"],
      "B": ["DC.element", "DC.wing", "RD.crew", "EC.team"]
    },
    "names": {
      "Kestrel": ["CA.colony", "DC.fleet", "EC.expedition"],
      "Amber": ["CA.colony", "RD.operation"],
      "Horizon": ["EC.expedition", "CA.settlement"]
    }
  },
  "structural_signals": {
    "branch_unique_terms": {
      "Squadron": "defense_command",
      "Wing": "defense_command",
      "Element": "defense_command",
      "Colony": "colonial_administration",
      "District": "colonial_administration",
      "Settlement": "colonial_administration",
      "Expedition": "expeditionary_corps",
      "Team": "expeditionary_corps",
      "Operation": "resource_directorate",
      "Facility": "resource_directorate",
      "Crew": "resource_directorate"
    },
    "depth_constraints": {
      "5": ["defense_command"],
      "4": ["colonial_administration", "resource_directorate"],
      "3": ["expeditionary_corps"]
    }
  }
}
```

**Key points:**
- Include `collision_index` mapping every shared designator to all possible meanings
- Include `structural_signals` for Layer 3 inference
- Mark branch-unique level names

#### Task 1.2: synthetic_vocabulary.json

Rewrite with Terraform Combine vocabulary.

```json
{
  "meta": {"version": "4.1.0", "setting": "terraform_combine"},
  "situational": {
    "defense_patrol": ["CONTACT", "INTERCEPT", "PATROL", "ALERT", "VECTOR", "RTB"],
    "defense_garrison": ["STATION", "GARRISON", "POST", "WATCH", "RELIEF"],
    "colonial_founding": ["FOUNDING", "SETTLEMENT", "ESTABLISH", "CHARTER"],
    "expeditionary_survey": ["SURVEY", "BEACON", "CHARTING", "PROBE"],
    "resource_extraction": ["EXTRACTION", "YIELD", "SHIFT", "DRILL", "HAUL"]
  },
  "clutter": {
    "transport": ["Deck-2", "Bay-C", "Berth-17", "Hold-3", "Airlock-7"],
    "medical": ["Ward-3", "Bed-17", "Triage-2", "Intake-442"],
    "processing": ["Queue-7", "Line-23", "Proc-2", "Grp-4"],
    "operations": ["Station-42", "Post-7", "Watch-3", "Console-B"]
  },
  "confounders": {
    "letters": ["A", "B", "C", "D"],
    "numbers": ["7", "3", "12"],
    "codes": ["C-4", "2A", "B-7"]
  }
}
```

#### Task 1.3: synthetic_themes.json

Rewrite with branch-based themes.

```json
{
  "meta": {"version": "4.1.0"},
  "themes": {
    "defense_command": {
      "situations": ["patrol_incursion", "patrol_routine", "station_defense", "fleet_transit"],
      "vocabulary_pool": "defense_*",
      "clerk_archetypes": ["defense_squadron", "defense_operations", "fleet_rushed", "fleet_methodical"]
    }
  }
}
```

### Phase 2: Models Update

#### Task 2.1: models.py

Add state model, difficulty fields, update enums.

**New/modified classes:**

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional

class Branch(Enum):
    """Terraform Combine branches."""
    COLONIAL_ADMINISTRATION = "colonial_administration"
    DEFENSE_COMMAND = "defense_command"
    EXPEDITIONARY_CORPS = "expeditionary_corps"
    RESOURCE_DIRECTORATE = "resource_directorate"

class TransferScope(Enum):
    """Scope of a transfer between states."""
    WITHIN_LEVEL3 = "within_level3"
    WITHIN_LEVEL2 = "within_level2"
    WITHIN_BRANCH = "within_branch"
    CROSS_BRANCH = "cross_branch"

class CollisionSeverity(Enum):
    """Severity of collision zone for a post."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CROSS_BRANCH = "cross_branch"

class DifficultyTier(Enum):
    """Soldier-level difficulty tier."""
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    EXTREME = "extreme"

class FamiliarityLevel(Enum):
    """Familiarity level for rendering."""
    SAME_L3 = "same_level3"
    SAME_L2 = "same_level2"
    SAME_BRANCH = "same_branch"
    DIFFERENT_BRANCH = "different_branch"

@dataclass
class State:
    """
    A single state in a soldier's service.
    
    Each state represents a temporal segment where the soldier
    was assigned to a specific post.
    """
    state_id: str               # Unique ID: "{soldier_id}-{state_order}"
    soldier_id: str             # Parent soldier
    state_order: int            # 1, 2, or 3
    branch: Branch              # Which branch
    post_path: str              # Full path: "Alpha/Kestrel/3/A/7"
    post_levels: Dict[str, str] # {"sector": "Alpha", "fleet": "Kestrel", ...}
    
    # v4.1: Collision tracking
    collision_zone_flag: bool = False
    collision_severity: CollisionSeverity = CollisionSeverity.NONE
    colliding_paths: List[str] = field(default_factory=list)

@dataclass
class Soldier:
    """
    A soldier with 1-3 states.
    """
    soldier_id: str
    name_first: str
    name_middle: str
    name_last: str
    rank: str
    states: List[State]         # 1-3 states
    
    # v4.1: Difficulty metrics (computed post-generation)
    difficulty_tier: Optional[DifficultyTier] = None
    complementarity_score: Optional[float] = None
    structural_resolvability: Optional[bool] = None

@dataclass
class Entry:
    """
    A single rendered record.
    """
    entry_id: str
    source_id: str
    soldier_id: str
    state_id: str               # Which state this record captures
    raw_text: str
    clerk_id: str
    situation_id: str
    quality_tier: int           # 1-5 (Layer 1)
    
    # v4.1: Completeness tracking
    path_completeness: float = 0.0          # 0.0-1.0
    levels_provided: List[str] = field(default_factory=list)
    extraction_signals: List[str] = field(default_factory=list)

@dataclass
class Source:
    """
    A source document (manifest page, personnel list, etc.)
    """
    source_id: str
    clerk_id: str
    situation_id: str
    quality_tier: int
    home_unit: str              # Level-3 path for familiarity
    temporal_anchor: int        # 1, 2, or 3
```

### Phase 3: Core Components

#### Task 3.1: hierarchy_loader.py

Support variable-depth branches and collision queries.

```python
class HierarchyLoader:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self._collision_index = self.config.get("collision_index", {})
        self._structural_signals = self.config.get("structural_signals", {})
    
    def get_branch_depth(self, branch: Branch) -> int:
        """Return depth for a branch (3, 4, or 5)."""
        return self.config["branches"][branch.value]["depth"]
    
    def get_collision_severity(
        self,
        branch: Branch,
        post_levels: Dict[str, str]
    ) -> CollisionSeverity:
        """
        Determine collision severity for a post.
        
        Checks each designator against collision index to see
        how many other posts could have the same partial path.
        """
        # Implementation: check each level's designator against collision_index
        # Return severity based on how many collisions exist
        pass
    
    def get_colliding_paths(
        self,
        branch: Branch,
        post_levels: Dict[str, str]
    ) -> List[str]:
        """Return list of other posts this could be confused with."""
        pass
    
    def get_structural_signals_for_branch(self, branch: Branch) -> List[str]:
        """Return level names unique to this branch."""
        return [
            term for term, b in self._structural_signals["branch_unique_terms"].items()
            if b == branch.value
        ]
```

#### Task 3.2: soldier_factory.py

State generation with collision zone tagging.

```python
class SoldierFactory:
    def __init__(
        self,
        hierarchy: HierarchyLoader,
        rng: np.random.Generator
    ):
        self.hierarchy = hierarchy
        self.rng = rng
        self.transfer_manager = TransferManager(hierarchy, rng)
    
    def create_soldier(self, soldier_id: str) -> Soldier:
        """Create a soldier with 1-3 states."""
        # 1. Generate identity
        name_first, name_middle, name_last = self._generate_name()
        rank = self._generate_rank()
        
        # 2. Determine state count
        state_count = self._sample_state_count()  # 1, 2, or 3
        
        # 3. Generate states
        states = self._generate_states(soldier_id, state_count)
        
        return Soldier(
            soldier_id=soldier_id,
            name_first=name_first,
            name_middle=name_middle,
            name_last=name_last,
            rank=rank,
            states=states,
        )
    
    def _generate_states(
        self,
        soldier_id: str,
        state_count: int
    ) -> List[State]:
        """Generate 1-3 states with transfers."""
        states = []
        
        # First state
        branch = self._sample_branch()
        post_levels = self._generate_post(branch)
        states.append(self._create_state(
            soldier_id, 1, branch, post_levels
        ))
        
        # Additional states (transfers)
        for i in range(1, state_count):
            transfer_scope = self._sample_transfer_scope()
            branch, post_levels = self.transfer_manager.apply_transfer(
                states[-1].branch,
                states[-1].post_levels,
                transfer_scope
            )
            states.append(self._create_state(
                soldier_id, i + 1, branch, post_levels
            ))
        
        return states
    
    def _create_state(
        self,
        soldier_id: str,
        state_order: int,
        branch: Branch,
        post_levels: Dict[str, str]
    ) -> State:
        """Create a state with collision zone tagging."""
        post_path = self._build_post_path(branch, post_levels)
        
        # v4.1: Tag collision zone
        collision_severity = self.hierarchy.get_collision_severity(branch, post_levels)
        collision_zone_flag = collision_severity != CollisionSeverity.NONE
        colliding_paths = self.hierarchy.get_colliding_paths(branch, post_levels)
        
        return State(
            state_id=f"{soldier_id}-{state_order}",
            soldier_id=soldier_id,
            state_order=state_order,
            branch=branch,
            post_path=post_path,
            post_levels=post_levels,
            collision_zone_flag=collision_zone_flag,
            collision_severity=collision_severity,
            colliding_paths=colliding_paths,
        )
    
    def _sample_state_count(self) -> int:
        """Sample state count: 65% one, 28% two, 7% three."""
        return self.rng.choice([1, 2, 3], p=[0.65, 0.28, 0.07])
    
    def _sample_transfer_scope(self) -> TransferScope:
        """Sample transfer scope."""
        return self.rng.choice(
            list(TransferScope),
            p=[0.50, 0.30, 0.15, 0.05]  # within_l3, within_l2, within_branch, cross_branch
        )
```

#### Task 3.3: source_generator.py

Add home_unit and temporal_anchor.

```python
@dataclass
class Source:
    source_id: str
    clerk_id: str
    situation_id: str
    quality_tier: int
    home_unit: str          # Level-3 path (e.g., "Alpha/Kestrel/3")
    temporal_anchor: int    # 1, 2, or 3

class SourceGenerator:
    def create_source(
        self,
        source_id: str,
        clerk: Clerk,
        situation: Situation,
    ) -> Source:
        """Create a source with home unit and temporal anchor."""
        home_unit = self._assign_home_unit(clerk, situation)
        temporal_anchor = self._assign_temporal_anchor()
        quality_tier = self._assign_quality_tier(clerk)
        
        return Source(
            source_id=source_id,
            clerk_id=clerk.clerk_id,
            situation_id=situation.situation_id,
            quality_tier=quality_tier,
            home_unit=home_unit,
            temporal_anchor=temporal_anchor,
        )
    
    def _assign_temporal_anchor(self) -> int:
        """Assign temporal anchor (which state period this source captures)."""
        # Uniform distribution across possible state orders
        return self.rng.integers(1, 4)  # 1, 2, or 3
```

#### Task 3.4: renderer.py

Familiarity-aware rendering with completeness tracking.

```python
class Renderer:
    def __init__(self, hierarchy: HierarchyLoader):
        self.hierarchy = hierarchy
    
    def render_entry(
        self,
        soldier: Soldier,
        state: State,
        source: Source,
        clerk: Clerk,
    ) -> Entry:
        """Render a soldier's state for a source."""
        # 1. Calculate familiarity
        familiarity = self._calculate_familiarity(state, source.home_unit)
        
        # 2. Render unit string based on familiarity
        unit_string = self._render_unit_string(state, clerk, familiarity)
        
        # 3. Render full entry
        raw_text = self._apply_clerk_template(soldier, state, unit_string, clerk)
        
        # v4.1: Track completeness
        levels_provided = self._extract_levels_provided(unit_string, state.branch)
        path_completeness = len(levels_provided) / self.hierarchy.get_branch_depth(state.branch)
        extraction_signals = self._extract_structural_signals(unit_string, state.branch)
        
        return Entry(
            entry_id=f"{source.source_id}-{soldier.soldier_id}",
            source_id=source.source_id,
            soldier_id=soldier.soldier_id,
            state_id=state.state_id,
            raw_text=raw_text,
            clerk_id=clerk.clerk_id,
            situation_id=source.situation_id,
            quality_tier=source.quality_tier,
            path_completeness=path_completeness,
            levels_provided=levels_provided,
            extraction_signals=extraction_signals,
        )
    
    def _calculate_familiarity(
        self,
        state: State,
        home_unit: str,
    ) -> FamiliarityLevel:
        """
        Determine familiarity level.
        
        Compare state's post path to source's home unit.
        home_unit is Level-3 path: "Sector/Level2/Level3"
        """
        state_l3_path = self._get_l3_path(state)
        state_l2_path = self._get_l2_path(state)
        state_branch = state.branch
        
        home_parts = home_unit.split("/")
        home_l3_path = home_unit
        home_l2_path = "/".join(home_parts[:2]) if len(home_parts) >= 2 else home_unit
        
        if state_l3_path == home_l3_path:
            return FamiliarityLevel.SAME_L3
        elif state_l2_path == home_l2_path:
            return FamiliarityLevel.SAME_L2
        elif self._same_branch(state_branch, home_unit):
            return FamiliarityLevel.SAME_BRANCH
        else:
            return FamiliarityLevel.DIFFERENT_BRANCH
    
    def _render_unit_string(
        self,
        state: State,
        clerk: Clerk,
        familiarity: FamiliarityLevel,
    ) -> str:
        """
        Render unit string with familiarity-based detail.
        
        SAME_L3: Minimal - just lowest level(s)
        SAME_L2: Low - lowest + level-3
        SAME_BRANCH: Medium - up through level-2
        DIFFERENT_BRANCH: Maximum - full path with branch
        """
        # Apply clerk's format template
        # Truncate based on familiarity level
        # Return rendered string
        pass
    
    def _extract_levels_provided(
        self,
        unit_string: str,
        branch: Branch,
    ) -> List[str]:
        """
        Determine which hierarchy levels are present in the rendered string.
        
        v4.1: Required for complementarity analysis.
        """
        levels = []
        branch_config = self.hierarchy.get_branch_config(branch)
        
        for level_name in branch_config["levels"]:
            if self._level_appears_in_string(level_name, unit_string, branch_config):
                levels.append(level_name)
        
        return levels
    
    def _extract_structural_signals(
        self,
        unit_string: str,
        branch: Branch,
    ) -> List[str]:
        """
        Extract structural signals that aid disambiguation.
        
        v4.1: Required for Layer 3 analysis.
        """
        signals = []
        
        # Check for branch-unique level names
        unique_terms = self.hierarchy.get_structural_signals_for_branch(branch)
        for term in unique_terms:
            if term.lower() in unit_string.lower():
                signals.append(f"branch_unique:{term}")
        
        # Check for depth indicators
        level_count = len(self._extract_levels_provided(unit_string, branch))
        if level_count >= 4:
            signals.append("depth:4+")
        if level_count == 5:
            signals.append("depth:5")  # Must be Defense Command
        
        return signals
```

### Phase 4: New Difficulty Components (v4.1)

#### Task 4.1: completeness_analyzer.py (NEW)

```python
"""
Analyze record path coverage for complementarity computation.
"""
from typing import List, Dict, Set
from .models import Entry, Soldier, State

class CompletenessAnalyzer:
    """Analyzes path coverage across records for a soldier."""
    
    def analyze_soldier_records(
        self,
        soldier: Soldier,
        entries: List[Entry],
    ) -> Dict[str, any]:
        """
        Analyze all records for a soldier.
        
        Returns:
            {
                "total_levels": int,
                "covered_levels": Set[str],
                "coverage_by_state": Dict[state_id, Set[str]],
                "redundancy_count": Dict[str, int],
                "complementarity_score": float,
            }
        """
        # Group entries by state
        entries_by_state = self._group_by_state(entries)
        
        results = {
            "coverage_by_state": {},
            "redundancy_count": {},
        }
        
        for state_id, state_entries in entries_by_state.items():
            state = self._get_state(soldier, state_id)
            branch_depth = self._get_branch_depth(state.branch)
            
            # Compute coverage for this state
            covered_levels: Set[str] = set()
            level_counts: Dict[str, int] = {}
            
            for entry in state_entries:
                for level in entry.levels_provided:
                    covered_levels.add(level)
                    level_counts[level] = level_counts.get(level, 0) + 1
            
            results["coverage_by_state"][state_id] = covered_levels
            results["redundancy_count"][state_id] = level_counts
        
        # Compute complementarity score
        results["complementarity_score"] = self._compute_complementarity(
            soldier, results
        )
        
        return results
    
    def _compute_complementarity(
        self,
        soldier: Soldier,
        analysis: Dict,
    ) -> float:
        """
        Compute complementarity score (0.0-1.0).
        
        High score = records cover different levels (complementary)
        Low score = records cover same levels (redundant)
        
        Formula: coverage_breadth / (1 + redundancy_penalty)
        """
        total_coverage = 0.0
        total_redundancy = 0.0
        
        for state in soldier.states:
            state_id = state.state_id
            branch_depth = self._get_branch_depth(state.branch)
            
            covered = analysis["coverage_by_state"].get(state_id, set())
            counts = analysis["redundancy_count"].get(state_id, {})
            
            # Coverage breadth: fraction of levels covered
            coverage = len(covered) / branch_depth
            
            # Redundancy penalty: average over-coverage
            if counts:
                avg_count = sum(counts.values()) / len(counts)
                redundancy = max(0, avg_count - 1) / avg_count
            else:
                redundancy = 0
            
            total_coverage += coverage
            total_redundancy += redundancy
        
        n_states = len(soldier.states)
        avg_coverage = total_coverage / n_states
        avg_redundancy = total_redundancy / n_states
        
        # Complementarity formula
        return avg_coverage / (1 + avg_redundancy)
```

#### Task 4.2: difficulty_computer.py (NEW)

```python
"""
Compute soldier-level difficulty from three layers.
"""
from typing import List, Dict
from .models import (
    Soldier, Entry, State,
    DifficultyTier, CollisionSeverity
)
from .completeness_analyzer import CompletenessAnalyzer

class DifficultyComputer:
    """Computes soldier-level difficulty tier."""
    
    def __init__(self, completeness_analyzer: CompletenessAnalyzer):
        self.completeness_analyzer = completeness_analyzer
    
    def compute_difficulty(
        self,
        soldier: Soldier,
        entries: List[Entry],
    ) -> Soldier:
        """
        Compute difficulty metrics and tier for a soldier.
        
        Updates soldier in-place and returns it.
        """
        # Step 1: Check collision zone (from State)
        collision_zone = any(state.collision_zone_flag for state in soldier.states)
        max_collision_severity = max(
            (state.collision_severity for state in soldier.states),
            key=lambda x: list(CollisionSeverity).index(x),
            default=CollisionSeverity.NONE
        )
        
        # Step 2: Compute complementarity (Layer 2)
        analysis = self.completeness_analyzer.analyze_soldier_records(soldier, entries)
        complementarity_score = analysis["complementarity_score"]
        
        # Step 3: Check structural resolvability (Layer 3)
        structural_resolvability = self._check_structural_resolvability(entries)
        
        # Step 4: Check if any record is complete (Layer 1 sufficient)
        any_complete = any(entry.path_completeness >= 0.95 for entry in entries)
        
        # Step 5: Assign difficulty tier
        difficulty_tier = self._assign_tier(
            any_complete=any_complete,
            collision_zone=collision_zone,
            collision_severity=max_collision_severity,
            complementarity_score=complementarity_score,
            structural_resolvability=structural_resolvability,
        )
        
        # Update soldier
        soldier.difficulty_tier = difficulty_tier
        soldier.complementarity_score = complementarity_score
        soldier.structural_resolvability = structural_resolvability
        
        return soldier
    
    def _check_structural_resolvability(self, entries: List[Entry]) -> bool:
        """
        Check if structural signals can resolve ambiguity.
        
        Returns True if any entry has branch-unique signals.
        """
        for entry in entries:
            for signal in entry.extraction_signals:
                if signal.startswith("branch_unique:"):
                    return True
                if signal == "depth:5":  # Only DC has depth 5
                    return True
        return False
    
    def _assign_tier(
        self,
        any_complete: bool,
        collision_zone: bool,
        collision_severity: CollisionSeverity,
        complementarity_score: float,
        structural_resolvability: bool,
    ) -> DifficultyTier:
        """
        Assign difficulty tier based on three layers.
        """
        # EASY: Any layer sufficient
        if any_complete:
            return DifficultyTier.EASY
        if complementarity_score > 0.8 and not collision_zone:
            return DifficultyTier.EASY
        if structural_resolvability and complementarity_score > 0.5:
            return DifficultyTier.EASY
        
        # MODERATE: Combination works
        if not collision_zone and complementarity_score > 0.5:
            return DifficultyTier.MODERATE
        if collision_zone and complementarity_score > 0.6:
            return DifficultyTier.MODERATE
        if structural_resolvability:
            return DifficultyTier.MODERATE
        
        # EXTREME: Worst case
        if collision_severity == CollisionSeverity.CROSS_BRANCH:
            if complementarity_score < 0.3:
                return DifficultyTier.EXTREME
        if collision_zone and complementarity_score < 0.3:
            return DifficultyTier.EXTREME
        
        # HARD: Default for collision + low complementarity
        return DifficultyTier.HARD
```

#### Task 4.3: difficulty_rebalancer.py (NEW)

```python
"""
Adjust generation to hit target difficulty distribution.
"""
from typing import List, Dict, Tuple
from .models import Soldier, Entry, DifficultyTier

class DifficultyRebalancer:
    """Rebalances generated data to hit target difficulty distribution."""
    
    TARGET_DISTRIBUTION = {
        DifficultyTier.EASY: 0.50,
        DifficultyTier.MODERATE: 0.30,
        DifficultyTier.HARD: 0.15,
        DifficultyTier.EXTREME: 0.05,
    }
    TOLERANCE = 0.05
    
    def needs_rebalancing(
        self,
        soldiers: List[Soldier],
    ) -> bool:
        """Check if current distribution is outside tolerance."""
        actual = self._compute_distribution(soldiers)
        
        for tier, target in self.TARGET_DISTRIBUTION.items():
            if abs(actual.get(tier, 0) - target) > self.TOLERANCE:
                return True
        return False
    
    def identify_adjustments(
        self,
        soldiers: List[Soldier],
    ) -> Dict[str, any]:
        """
        Identify what adjustments are needed.
        
        Returns:
            {
                "over_represented": List[DifficultyTier],
                "under_represented": List[DifficultyTier],
                "soldiers_to_adjust": List[soldier_id],
                "adjustment_strategy": str,
            }
        """
        actual = self._compute_distribution(soldiers)
        
        over = [t for t, target in self.TARGET_DISTRIBUTION.items()
                if actual.get(t, 0) > target + self.TOLERANCE]
        under = [t for t, target in self.TARGET_DISTRIBUTION.items()
                 if actual.get(t, 0) < target - self.TOLERANCE]
        
        # Identify soldiers in over-represented tiers for adjustment
        soldiers_to_adjust = [
            s.soldier_id for s in soldiers
            if s.difficulty_tier in over
        ]
        
        return {
            "over_represented": over,
            "under_represented": under,
            "soldiers_to_adjust": soldiers_to_adjust[:len(soldiers_to_adjust) // 2],  # Adjust half
            "adjustment_strategy": self._determine_strategy(over, under),
        }
    
    def _determine_strategy(
        self,
        over: List[DifficultyTier],
        under: List[DifficultyTier],
    ) -> str:
        """Determine adjustment strategy."""
        if DifficultyTier.EASY in over and DifficultyTier.HARD in under:
            return "move_to_collision_zone"
        if DifficultyTier.HARD in over and DifficultyTier.EASY in under:
            return "add_complementary_records"
        return "regenerate_selected"
    
    def _compute_distribution(
        self,
        soldiers: List[Soldier],
    ) -> Dict[DifficultyTier, float]:
        """Compute actual difficulty distribution."""
        counts = {tier: 0 for tier in DifficultyTier}
        for soldier in soldiers:
            if soldier.difficulty_tier:
                counts[soldier.difficulty_tier] += 1
        
        total = len(soldiers)
        return {tier: count / total for tier, count in counts.items()}
```

### Phase 5: Pipeline Integration

#### Task 5.1: pipeline.py

Wire state assignment and difficulty computation.

```python
from .soldier_factory import SoldierFactory
from .source_generator import SourceGenerator
from .renderer import Renderer
from .completeness_analyzer import CompletenessAnalyzer
from .difficulty_computer import DifficultyComputer
from .difficulty_rebalancer import DifficultyRebalancer

def generate_dataset(
    config: Dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Generate v4.1 synthetic dataset.
    
    Returns:
        (raw_df, validation_df, sources_df)
    """
    hierarchy = HierarchyLoader(config["hierarchy_path"])
    soldier_factory = SoldierFactory(hierarchy, rng)
    source_generator = SourceGenerator(hierarchy, rng)
    renderer = Renderer(hierarchy)
    completeness_analyzer = CompletenessAnalyzer()
    difficulty_computer = DifficultyComputer(completeness_analyzer)
    rebalancer = DifficultyRebalancer()
    
    # 1. Create soldiers with states
    soldiers = [
        soldier_factory.create_soldier(f"S{i:04d}")
        for i in range(config["n_soldiers"])
    ]
    
    # 2. Create sources with temporal anchors
    sources = [
        source_generator.create_source(f"SRC{i:04d}", clerk, situation)
        for i, (clerk, situation) in enumerate(source_assignments)
    ]
    
    # 3. Generate entries
    all_entries = []
    for soldier in soldiers:
        soldier_entries = []
        for source in _get_sources_for_soldier(soldier, sources):
            # Use temporal_anchor to select state
            state = _select_state_for_source(soldier, source)
            entry = renderer.render_entry(soldier, state, source, clerk)
            soldier_entries.append(entry)
            all_entries.append(entry)
        
        # 4. Compute difficulty for this soldier
        difficulty_computer.compute_difficulty(soldier, soldier_entries)
    
    # 5. Check if rebalancing needed
    if rebalancer.needs_rebalancing(soldiers):
        adjustments = rebalancer.identify_adjustments(soldiers)
        # Apply adjustments (regenerate selected soldiers)
        # ... rebalancing logic ...
    
    # 6. Build output DataFrames
    raw_df = _build_raw_df(all_entries)
    validation_df = _build_validation_df(soldiers)
    sources_df = _build_sources_df(sources)
    
    return raw_df, validation_df, sources_df

def _build_raw_df(entries: List[Entry]) -> pd.DataFrame:
    """Build raw.parquet schema."""
    return pd.DataFrame([
        {
            "source_id": e.source_id,
            "soldier_id": e.soldier_id,
            "state_id": e.state_id,
            "raw_text": e.raw_text,
            "clerk_id": e.clerk_id,
            "situation_id": e.situation_id,
            "quality_tier": e.quality_tier,
            # v4.1 additions
            "path_completeness": e.path_completeness,
            "levels_provided": e.levels_provided,
            "extraction_signals": e.extraction_signals,
        }
        for e in entries
    ])

def _build_validation_df(soldiers: List[Soldier]) -> pd.DataFrame:
    """Build validation.parquet schema."""
    rows = []
    for soldier in soldiers:
        for state in soldier.states:
            rows.append({
                "soldier_id": soldier.soldier_id,
                "state_id": state.state_id,
                "state_order": state.state_order,
                "branch": state.branch.value,
                "post_path": state.post_path,
                **state.post_levels,
                # v4.1 additions
                "collision_zone_flag": state.collision_zone_flag,
                "collision_severity": state.collision_severity.value,
                "soldier_difficulty_tier": soldier.difficulty_tier.value if soldier.difficulty_tier else None,
                "complementarity_score": soldier.complementarity_score,
                "structural_resolvability": soldier.structural_resolvability,
            })
    return pd.DataFrame(rows)
```

---

## Warnings and Pitfalls

### Domain Knowledge Pitfall

**DO NOT** use any real military terminology, unit names, or organizational patterns. The whole point is domain decontamination.

### Hierarchy Depth Pitfall

**Each branch has different depth.** Never hardcode 4 levels:
- Defense Command: 5 levels
- Colonial Admin: 4 levels
- Resource Directorate: 4 levels
- Expeditionary Corps: 3 levels

### State vs Assignment Pitfall

**v3 had Assignments. v4 has States.** Don't conflate them.

### Quality ≠ Difficulty Pitfall (v4.1)

**This is critical.** Quality tier measures Layer 1 only. A Tier-1 record can be HARD if it's in a collision zone. A Tier-5 record can be EASY if complementary.

### Familiarity Pitfall

**Familiarity is relative to SOURCE, not to SOLDIER.** The soldier hasn't changed; the source's perspective determines rendering.

### Collision Pitfall

**Collisions must be meaningful.** Ensure the collision index accurately reflects overlaps.

### Completeness Tracking Pitfall (v4.1)

**Track completeness AFTER rendering.** The renderer must analyze what it produced, not what it intended to produce. Familiarity truncation affects completeness.

### Difficulty Computation Order Pitfall (v4.1)

**Compute difficulty AFTER all records for a soldier exist.** Complementarity requires seeing all records. Don't compute per-record.

---

## Acceptance Criteria

### Config Files

- [ ] `hierarchy_reference.json` defines all 4 branches with correct depths
- [ ] `hierarchy_reference.json` has collision_index mapping shared designators
- [ ] `hierarchy_reference.json` has structural_signals for Layer 3
- [ ] `synthetic_vocabulary.json` has situational terms for all branches
- [ ] `synthetic_vocabulary.json` has clutter and confounders
- [ ] `synthetic_themes.json` maps branches to situations and archetypes

### Models

- [ ] `State` dataclass has collision fields (collision_zone_flag, collision_severity, colliding_paths)
- [ ] `Soldier` dataclass has difficulty fields (difficulty_tier, complementarity_score, structural_resolvability)
- [ ] `Entry` dataclass has completeness fields (path_completeness, levels_provided, extraction_signals)
- [ ] `CollisionSeverity` enum has all 5 levels
- [ ] `DifficultyTier` enum has all 4 tiers
- [ ] `FamiliarityLevel` enum has all 4 levels

### Generation Logic

- [ ] `hierarchy_loader.py` can compute collision severity for a post
- [ ] `soldier_factory.py` tags collision zones at state creation
- [ ] `renderer.py` tracks levels_provided and extraction_signals
- [ ] `renderer.py` computes path_completeness

### Difficulty Components (v4.1)

- [ ] `completeness_analyzer.py` computes complementarity_score
- [ ] `difficulty_computer.py` computes difficulty_tier from all three layers
- [ ] `difficulty_rebalancer.py` identifies when rebalancing is needed
- [ ] Pipeline wires difficulty computation after record generation

### Output Schema

- [ ] `raw.parquet` includes path_completeness, levels_provided, extraction_signals
- [ ] `validation.parquet` includes collision_zone_flag, collision_severity
- [ ] `validation.parquet` includes soldier_difficulty_tier, complementarity_score, structural_resolvability

### Distribution Targets

- [ ] Generated dataset has ~50% easy, ~30% moderate, ~15% hard, ~5% extreme (±5%)
- [ ] Rebalancer triggers if distribution is outside tolerance

---

## Test Strategy

### Unit Tests

1. **Collision severity**: Test severity computation for various post configurations
2. **Complementarity score**: Test with complementary vs redundant record sets
3. **Structural resolvability**: Test detection of branch-unique terms
4. **Difficulty tier assignment**: Test tier logic with various combinations
5. **Familiarity calculation**: Test all 4 familiarity levels
6. **Path completeness**: Test extraction of levels_provided

### Integration Tests

1. **Full pipeline run**: Generate small dataset (100 soldiers), verify all schema columns
2. **Difficulty distribution**: Verify distribution is within tolerance of targets
3. **Collision consistency**: Verify collision flags match collision index
4. **Cross-branch transfer**: Verify soldiers with cross-branch transfer have different branch structures

---

## References

- **ADR-007**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **ADR-006**: `docs/architecture/decisions/ADR-006_per-record-vs-per-soldier-difficulty.md`
- **Style spec (v4.1)**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.1.yaml`
- **Design doc**: `docs/components/synthetic_data_generation/CURRENT.md`
