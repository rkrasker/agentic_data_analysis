# 004: Synthetic Data v4 - Terraform Combine Implementation

**Status:** Ready for execution
**Created:** 2026-01-25
**Model:** Sonnet, thinking on
**Component:** src/synthetic/, config/

---

## Objective

Implement the v4 synthetic data generation system based on ADR-007. This replaces the WWII military domain with a fictional interstellar setting (Terraform Combine) to eliminate LLM pretraining contamination, and adds explicit state tracking for rigorous evaluation.

**This is a rewrite, not a refactor.** The logic patterns transfer from v3, but the domain, vocabulary, and hierarchy structures are all new.

---

## Context

### Why This Change

LLM testing revealed a critical confound: the model was resolving unit assignments using pretraining knowledge (Wikipedia, military histories) rather than disambiguation signals in our data. A fictional domain with zero pretraining presence gives clean attribution - if disambiguation succeeds, it's due to our signals, not background knowledge.

### What ADR-007 Decided

1. **Domain decontamination**: Replace WWII military with "Terraform Combine" - fictional interstellar organization
2. **Explicit states**: `state_id` in all schemas; soldiers have 1-3 states
3. **Source-anchored states**: Each source captures one state per soldier; conflicts arise across sources
4. **Familiarity gradient**: Clerks abbreviate for home unit, spell out foreign units
5. **Heterogeneous branches**: 4 branches with different hierarchy depths (3-5 levels)
6. **Cross-branch transfers**: 15% of transfers cross branch boundaries

### Reference Documents

- **ADR**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **Style spec**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.yaml`
- **Design doc**: `docs/components/synthetic_data_generation/CURRENT.md`

---

## Scope

### In Scope (This Instruction)

| File | Change |
|------|--------|
| `config/hierarchies/hierarchy_reference.json` | **Full rewrite** - Terraform Combine branches |
| `config/synthetic/synthetic_vocabulary.json` | **Full rewrite** - New situational/clutter/confounder terms |
| `config/synthetic/synthetic_themes.json` | **Full rewrite** - Branch-based themes |
| `src/synthetic/models.py` | **Significant update** - Add State model, update Assignment, update enums |
| `src/synthetic/hierarchy_loader.py` | **Update** - Support variable-depth branch hierarchies |
| `src/synthetic/soldier_factory.py` | **Significant update** - State generation, multi-state soldiers |
| `src/synthetic/source_generator.py` | **Update** - Add home_unit, temporal_anchor |
| `src/synthetic/renderer.py` | **Significant update** - Familiarity-aware rendering, new branches |
| `src/synthetic/clerk_factory.py` | **Update** - New archetype contexts |
| `src/synthetic/situation_manager.py` | **Update** - New situations |
| `src/synthetic/vocabulary_injector.py` | **Update** - Work with new vocabulary structure |
| `src/synthetic/transfer_manager.py` | **Update** - Cross-branch transfers, state model |
| `src/synthetic/pipeline.py` | **Update** - Wire state assignment |

### Out of Scope (Future Work)

- Creating `seed_set_v4.json` (hand-crafted examples)
- Running the generation pipeline
- Updating preprocessing to handle new domain
- Updating evaluation metrics
- Any changes to resolver or strategy code

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

---

## Implementation Tasks

### Phase 1: Config Files

#### Task 1.1: hierarchy_reference.json

Rewrite to define Terraform Combine structure.

```json
{
  "meta": {
    "version": "4.0.0",
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
        "colony": {"designator_style": "name", "values": ["Verdant", "Amber", "Kestrel", "Thornmark", ...]},
        "district": {"designator_style": "number", "values": ["1", "2", "3", "4", "5", "6", "7", "8"]},
        "settlement": {"designator_style": "name", "values": ["Haven", "Prospect", "Landfall", "Waypoint", ...]}
      }
    },
    // Similar for defense_command, expeditionary_corps, resource_directorate
  },
  "collision_index": {
    "numbers": {"7": ["DC.fleet", "CA.district", "RD.facility", "EC.team"], ...},
    "letters": {"A": ["DC.element", "DC.wing", "RD.crew", "EC.team"], ...},
    "names": {"Kestrel": ["CA.colony", "DC.fleet", "EC.expedition"], ...}
  }
}
```

**Key points:**
- Include enough variety for realistic generation (4+ colonies, 4+ fleets, etc.)
- Collision index should map every shared designator to all possible meanings
- Greek letters for sectors (Alpha, Beta, Gamma, Delta, Epsilon, Zeta)

#### Task 1.2: synthetic_vocabulary.json

Rewrite with Terraform Combine vocabulary.

```json
{
  "meta": {"version": "4.0.0", "setting": "terraform_combine"},
  "situational": {
    "defense_patrol": ["CONTACT", "INTERCEPT", "PATROL", "ALERT", "VECTOR", "RTB"],
    "defense_garrison": ["STATION", "GARRISON", "POST", "WATCH", "RELIEF"],
    "colonial_founding": ["FOUNDING", "SETTLEMENT", "ESTABLISH", "CHARTER"],
    "expeditionary_survey": ["SURVEY", "BEACON", "CHARTING", "PROBE"],
    "resource_extraction": ["EXTRACTION", "YIELD", "SHIFT", "DRILL", "HAUL"],
    // etc.
  },
  "clutter": {
    "transport": ["Deck-2", "Bay-C", "Berth-17", "Hold-3", "Airlock-7"],
    "medical": ["Ward-3", "Bed-17", "Triage-2", "Intake-442"],
    "processing": ["Queue-7", "Line-23", "Proc-2", "Grp-4"],
    "operations": ["Station-42", "Post-7", "Watch-3", "Console-B"]
  },
  "confounders": {
    "letters": ["A", "B", "C", "D"],  // Could be unit level or berth/bay
    "numbers": ["7", "3", "12"],      // Could be fleet/district/facility or queue/line
    "codes": ["C-4", "2A", "B-7"]     // Ambiguous format patterns
  }
}
```

#### Task 1.3: synthetic_themes.json

Rewrite with branch-based themes.

```json
{
  "meta": {"version": "4.0.0"},
  "themes": {
    "defense_command": {
      "situations": ["patrol_incursion", "patrol_routine", "station_defense", "fleet_transit"],
      "vocabulary_pool": "defense_*",
      "clerk_archetypes": ["defense_squadron", "defense_operations", "fleet_rushed", "fleet_methodical"]
    },
    // Similar for other branches
  }
}
```

### Phase 2: Models Update

#### Task 2.1: models.py

Add state model, update enums for new domain.

**New/modified classes:**

```python
class Branch(Enum):
    """Terraform Combine branches."""
    COLONIAL_ADMINISTRATION = "colonial_administration"
    DEFENSE_COMMAND = "defense_command"
    EXPEDITIONARY_CORPS = "expeditionary_corps"
    RESOURCE_DIRECTORATE = "resource_directorate"

class TransferScope(Enum):
    """Scope of a transfer between states."""
    WITHIN_LEVEL3 = "within_level3"      # Same squadron/district/team/facility
    WITHIN_LEVEL2 = "within_level2"      # Same fleet/colony/expedition/operation
    WITHIN_BRANCH = "within_branch"       # Same branch, different level-2
    CROSS_BRANCH = "cross_branch"         # Different branch

@dataclass
class State:
    """
    A single state in a soldier's service.

    Each state resolves to exactly one post (component path).
    Soldiers have 1-3 states.
    """
    state_id: str           # e.g., "S001-1", "S001-2"
    soldier_id: str
    state_order: int        # 1, 2, or 3
    branch: Branch
    post_path: Dict[str, str]  # Level name -> designator

@dataclass
class Assignment:
    """A soldier's unit assignment (v4: branch-aware)."""
    branch: Branch
    post_path: Dict[str, str]  # Flexible: {"sector": "Alpha", "fleet": "Kestrel", ...}

    def to_dict(self) -> Dict[str, Any]:
        return {"branch": self.branch.value, **self.post_path}

@dataclass
class Soldier:
    """v4: Soldiers have states, not just assignments."""
    primary_id: str
    name_first: str
    name_last: str
    name_middle: Optional[str]
    rank: str
    states: List[State]  # 1-3 states

@dataclass
class Source:
    """v4: Sources have home_unit and temporal_anchor."""
    source_id: str
    clerk_id: str
    situation_id: str
    quality_tier: int
    home_unit: str          # Level-3 path for familiarity gradient
    temporal_anchor: int    # Which state-period (1, 2, or 3) this source captures
    entry_ids: List[str] = field(default_factory=list)
    selected_vocabulary: List[str] = field(default_factory=list)

@dataclass
class Entry:
    """v4: Entries link to state_id."""
    entry_id: str
    source_id: str
    soldier_id: str
    state_id: str           # NEW: which state this record captures
    raw_text: str
    # ... rest unchanged
```

**Update UnitFormatStyle enum** for new formats:
- Remove WWII-specific: `AAF_STANDARD`, `COMPACT_AAF`, `MARINE_STANDARD`
- Add TFC-specific: `DC_STANDARD`, `CA_STANDARD`, `EC_STANDARD`, `RD_STANDARD`, `COMPACT_DC`, `COMPACT_RD`

### Phase 3: Core Module Updates

#### Task 3.1: hierarchy_loader.py

Support variable-depth hierarchies per branch.

```python
def load_branch_hierarchy(branch: Branch) -> BranchHierarchy:
    """Load hierarchy for a specific branch."""
    # Returns structure with level names, designator pools, depth

def get_valid_designators(branch: Branch, level: str) -> List[str]:
    """Get valid designators for a level in a branch."""

def validate_post_path(branch: Branch, post_path: Dict[str, str]) -> bool:
    """Validate that post_path is valid for branch."""
```

#### Task 3.2: soldier_factory.py

Generate soldiers with 1-3 states.

```python
def create_soldier(
    soldier_id: str,
    hierarchy: HierarchyReference,
    rng: np.random.Generator,
) -> Soldier:
    """Create a soldier with states."""
    state_count = _sample_state_count(rng)  # 1, 2, or 3 per distribution
    branch = _sample_branch(rng)

    states = []
    current_post = _generate_initial_post(branch, hierarchy, rng)
    states.append(State(
        state_id=f"{soldier_id}-1",
        soldier_id=soldier_id,
        state_order=1,
        branch=branch,
        post_path=current_post
    ))

    for i in range(1, state_count):
        transfer_scope = _sample_transfer_scope(rng)
        new_branch, new_post = _apply_transfer(
            branch, current_post, transfer_scope, hierarchy, rng
        )
        states.append(State(
            state_id=f"{soldier_id}-{i+1}",
            soldier_id=soldier_id,
            state_order=i+1,
            branch=new_branch,
            post_path=new_post
        ))
        branch, current_post = new_branch, new_post

    return Soldier(
        primary_id=soldier_id,
        name_first=_generate_first_name(rng),
        name_last=_generate_last_name(rng),
        name_middle=_generate_middle_name(rng),
        rank=_sample_rank(rng),
        states=states
    )
```

**State count distribution:**
- 1 state: 65%
- 2 states: 28%
- 3 states: 7%

**Transfer scope distribution:**
- Within same Level-3: 40%
- Within same Level-2: 30%
- Within same branch: 15%
- Cross-branch: 15%

#### Task 3.3: source_generator.py

Add home_unit and temporal_anchor.

```python
@dataclass
class Source:
    # existing fields...
    home_unit: str          # Level-3 path (e.g., "Alpha/Kestrel/3")
    temporal_anchor: int    # 1, 2, or 3

def create_source(...) -> Source:
    """Create a source with home unit and temporal anchor."""
    home_unit = _assign_home_unit(clerk_archetype, situation, hierarchy, rng)
    temporal_anchor = _assign_temporal_anchor(rng)
    # ...
```

#### Task 3.4: renderer.py

Familiarity-aware rendering is the most complex change.

```python
class Renderer:
    def render_entry(
        self,
        soldier: Soldier,
        state: State,
        source: Source,
        clerk: Clerk,
    ) -> str:
        """Render a soldier's state for a source."""
        familiarity = self._calculate_familiarity(state, source.home_unit)
        unit_string = self._render_unit_string(state, clerk, familiarity)
        # ... rest of rendering

    def _calculate_familiarity(
        self,
        state: State,
        home_unit: str,
    ) -> FamiliarityLevel:
        """
        Determine familiarity level.

        Returns: SAME_L3, SAME_L2, SAME_BRANCH, or DIFFERENT_BRANCH
        """
        # Compare state.post_path to home_unit
        # Return appropriate level

    def _render_unit_string(
        self,
        state: State,
        clerk: Clerk,
        familiarity: FamiliarityLevel,
    ) -> str:
        """
        Render unit string with familiarity-based detail.

        SAME_L3: Minimal - "Martinez A" (just element)
        SAME_L2: Low - "Martinez A/Sq-3"
        SAME_BRANCH: Medium - "Martinez A/Sq-3/Fleet-Kestrel"
        DIFFERENT_BRANCH: Maximum - full path with branch
        """
        # Apply clerk's format template
        # Truncate based on familiarity level
```

**Branch-specific rendering:**
- Defense Command: "Elem 7, Wing A, 3rd Sq, Fleet Kestrel" or "7/A/3/Kestrel"
- Colonial Admin: "Settlement Haven, 2nd District, Colony Verdant" or "Haven/2/Verdant"
- Expeditionary: "Team A, Expedition Horizon" or "A/Horizon"
- Resource: "Crew A, Facility 7, Operation Deepcore" or "A/7/Deepcore"

#### Task 3.5: transfer_manager.py

Support cross-branch transfers.

```python
def apply_transfer(
    current_branch: Branch,
    current_post: Dict[str, str],
    transfer_scope: TransferScope,
    hierarchy: HierarchyReference,
    rng: np.random.Generator,
) -> Tuple[Branch, Dict[str, str]]:
    """
    Apply a transfer to generate a new state.

    For CROSS_BRANCH: select a new branch and generate entirely new post.
    For others: modify appropriate levels within current branch.
    """
```

### Phase 4: Pipeline Integration

#### Task 4.1: pipeline.py

Wire state assignment through generation.

```python
def generate_dataset(...):
    """Generate v4 synthetic dataset."""
    # 1. Create soldiers with states
    # 2. Create sources with temporal anchors
    # 3. For each (soldier, source) pair:
    #    - Use source.temporal_anchor to select which state
    #    - Render using familiarity between state and source.home_unit
    # 4. Output raw.parquet with state_id column
    # 5. Output validation.parquet with state columns
```

---

## Warnings and Pitfalls

### Domain Knowledge Pitfall

**DO NOT** use any real military terminology, unit names, or organizational patterns. The whole point of v4 is domain decontamination. If you find yourself thinking "this is like a battalion" or "this should work like companies", stop and use the Terraform Combine terms.

### Hierarchy Depth Pitfall

**Each branch has different depth.** Code that assumes 4 levels everywhere will fail:
- Defense Command: 5 levels
- Colonial Admin: 4 levels
- Resource Directorate: 4 levels
- Expeditionary Corps: 3 levels

Always use `len(branch.levels)` or equivalent, never hardcode.

### State vs Assignment Pitfall

**v3 had Assignments. v4 has States.** Don't conflate them:
- State = temporal segment with a post
- Post = the unit path within a state
- A soldier has 1-3 States, each State has exactly 1 post

### Familiarity Pitfall

**Familiarity is relative to SOURCE, not to SOLDIER.** A soldier in Fleet Kestrel appears abbreviated in a Kestrel source but spelled out in a Verdant source. The soldier hasn't changed; the source's perspective determines rendering.

### Collision Pitfall

**Collisions must be meaningful.** Don't just make designators overlap randomly. Ensure:
- The same number/letter/name appears at comparable levels across branches
- A record using just "7" or "A" could genuinely belong to multiple branches
- The collision index accurately reflects these overlaps

### Transfer Scope Pitfall

Cross-branch transfers create states with **different hierarchy structures**. A soldier transferring from Defense Command (5 levels) to Expeditionary Corps (3 levels) will have states that look structurally different. The renderer must handle this.

---

## Acceptance Criteria

### Config Files

- [ ] `hierarchy_reference.json` defines all 4 branches with correct depths
- [ ] `hierarchy_reference.json` has collision_index mapping shared designators
- [ ] `synthetic_vocabulary.json` has situational terms for all branches
- [ ] `synthetic_vocabulary.json` has clutter and confounders
- [ ] `synthetic_themes.json` maps branches to situations and archetypes

### Models

- [ ] `State` dataclass exists with state_id, soldier_id, state_order, branch, post_path
- [ ] `Soldier.states` is a List[State] with 1-3 items
- [ ] `Source.home_unit` and `Source.temporal_anchor` fields exist
- [ ] `Entry.state_id` field exists
- [ ] `Branch` enum has all 4 branches
- [ ] `TransferScope` enum has all 4 scopes

### Generation Logic

- [ ] `soldier_factory.py` generates soldiers with 1-3 states per distribution
- [ ] `soldier_factory.py` applies transfer logic for multi-state soldiers
- [ ] `source_generator.py` assigns home_unit and temporal_anchor
- [ ] `renderer.py` calculates familiarity correctly
- [ ] `renderer.py` renders all 4 branch formats
- [ ] `renderer.py` truncates based on familiarity level
- [ ] `transfer_manager.py` handles cross-branch transfers

### Output Schema

- [ ] Generated `raw.parquet` includes `state_id` column
- [ ] Generated `validation.parquet` includes `state_id`, `state_order`, `branch` columns
- [ ] Output is runnable (pipeline executes without error)

### No Regressions

- [ ] Existing tests pass (after updating for new domain)
- [ ] Quality tier system still works
- [ ] Vocabulary injection still works
- [ ] Clerk archetype rendering still works

---

## Test Strategy

### Unit Tests

1. **State generation**: Verify state count distribution matches spec
2. **Transfer scope**: Verify transfer scope distribution matches spec
3. **Hierarchy depth**: Verify each branch has correct depth
4. **Familiarity calculation**: Test all 4 familiarity levels
5. **Branch rendering**: Test render output for each branch format

### Integration Tests

1. **Full pipeline run**: Generate small dataset (100 soldiers), verify output schema
2. **State consistency**: Verify all records for a soldier in a source have same state_id
3. **Cross-branch transfer**: Verify soldiers with cross-branch transfer have states in different branches

---

## References

- **ADR**: `docs/architecture/decisions/ADR-007-synthetic-data-redesign.md`
- **Style spec (v4)**: `docs/components/synthetic_data_generation/synthetic_style_spec_v4.yaml`
- **Design doc**: `docs/components/synthetic_data_generation/CURRENT.md`
- **This decision extract**: `.project_history/extracts/raw/2026-01-25_opus_synthetic-v4-design.md`
