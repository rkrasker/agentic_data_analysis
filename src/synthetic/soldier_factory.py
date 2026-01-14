"""
SoldierFactory: Generate soldier truth records.

Creates soldiers with realistic name distributions and
assigns them to units based on hierarchy constraints.
"""

import random
from typing import Dict, List, Optional, Any

from .models import Soldier, Assignment
from .hierarchy_loader import HierarchyLoader


# Common WWII-era first names
FIRST_NAMES_MALE = [
    "James", "John", "Robert", "William", "Richard", "Charles", "Joseph", "Thomas",
    "George", "Edward", "Donald", "Frank", "Harold", "Paul", "Raymond", "Walter",
    "Henry", "Arthur", "Jack", "Albert", "Harry", "Ralph", "Eugene", "Carl",
    "Howard", "Fred", "Earl", "Roy", "Louis", "Anthony", "Leonard", "Stanley",
    "Lawrence", "Herbert", "Francis", "Samuel", "Kenneth", "Alfred", "Bernard",
    "Michael", "Daniel", "Gerald", "Peter", "Patrick", "Vincent", "Theodore",
]

# Common WWII-era last names (diverse representation)
LAST_NAMES = [
    # Anglo
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson",
    "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
    "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis",
    "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Scott", "Green",
    "Baker", "Adams", "Nelson", "Hill", "Campbell", "Mitchell", "Roberts", "Carter",
    # Irish
    "Murphy", "O'Brien", "Kelly", "Sullivan", "Ryan", "Walsh", "O'Connor", "Brennan",
    "Fitzgerald", "McCarthy", "Gallagher", "Quinn", "Doherty", "Kennedy", "Flynn",
    # Italian
    "Russo", "Martinelli", "Calabrese", "Romano", "Esposito", "Bianchi", "Ferrari",
    "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "Costa",
    # Polish
    "Kowalski", "Nowak", "Wojcik", "Kaminski", "Lewandowski", "Zielinski", "Szymanski",
    "Kozlowski", "Jankowski", "Wojciechowski", "Kwiatkowski", "Kaczmarek",
    # German
    "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz",
    "Hoffmann", "Koch", "Richter", "Klein", "Wolf", "Schroeder", "Neumann",
    # Jewish
    "Cohen", "Levy", "Goldberg", "Schwartz", "Shapiro", "Friedman", "Katz", "Rosen",
    "Kaplan", "Epstein", "Goldstein", "Silverman", "Weinstein", "Horowitz",
    # Scandinavian
    "Olson", "Peterson", "Larson", "Swanson", "Carlson", "Jensen", "Hansen", "Andersen",
    # Asian American
    "Chen", "Kim", "Lee", "Wong", "Tanaka", "Yamamoto", "Nakamura", "Suzuki",
    # Hispanic
    "Garcia", "Rodriguez", "Martinez", "Lopez", "Gonzalez", "Hernandez", "Perez",
    "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz",
]

# Middle initials distribution
MIDDLE_INITIALS = list("ABCDEFGHJKLMNOPRSTW")  # Common letters

# WWII rank distribution (enlisted, approximated)
RANKS = [
    ("Private", 0.30),
    ("Private First Class", 0.25),
    ("Corporal", 0.15),
    ("Sergeant", 0.12),
    ("Staff Sergeant", 0.08),
    ("Technical Sergeant", 0.04),
    ("Technician Fifth Grade", 0.03),
    ("Technician Fourth Grade", 0.02),
    ("First Lieutenant", 0.005),
    ("Second Lieutenant", 0.005),
    ("Captain", 0.002),
]


class SoldierFactory:
    """
    Factory for generating soldier truth records.

    Creates soldiers with realistic demographics and assigns
    them to valid unit positions based on hierarchy.
    """

    def __init__(
        self,
        hierarchy_loader: HierarchyLoader,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the factory.

        Args:
            hierarchy_loader: Loader for unit hierarchy data
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.hierarchy = hierarchy_loader
        self._soldier_counter = 0

        # Pre-compute rank weights
        self.rank_names = [r[0] for r in RANKS]
        self.rank_weights = [r[1] for r in RANKS]

    def _generate_soldier_id(self) -> str:
        """Generate a unique soldier ID."""
        self._soldier_counter += 1
        return f"S{self._soldier_counter:05d}"

    def create_soldier(
        self,
        component_id: str,
        regiment: Optional[str] = None,
        battalion: Optional[str] = None,
        company: Optional[str] = None,
    ) -> Soldier:
        """
        Create a soldier assigned to a specific unit.

        Args:
            component_id: The division/component to assign to
            regiment: Optional specific regiment (random if None)
            battalion: Optional specific battalion (random if None)
            company: Optional specific company (random if None)

        Returns:
            A new Soldier instance
        """
        soldier_id = self._generate_soldier_id()

        # Generate name
        first_name = self.rng.choice(FIRST_NAMES_MALE)
        last_name = self.rng.choice(LAST_NAMES)

        # Middle name (70% have one)
        if self.rng.random() < 0.70:
            middle_initial = self.rng.choice(MIDDLE_INITIALS)
            # Sometimes expand to full middle name
            middle_name = middle_initial if self.rng.random() < 0.8 else self._expand_middle(middle_initial)
        else:
            middle_name = None

        # Generate rank
        rank = self.rng.choices(self.rank_names, weights=self.rank_weights)[0]

        # Create assignment
        assignment = self._create_assignment(
            component_id, regiment, battalion, company
        )

        return Soldier(
            primary_id=soldier_id,
            name_first=first_name,
            name_last=last_name,
            name_middle=middle_name,
            rank=rank,
            assignment=assignment,
        )

    def _expand_middle(self, initial: str) -> str:
        """Expand a middle initial to a common name."""
        middle_names = {
            "A": ["Arthur", "Albert", "Andrew", "Anthony", "Allen"],
            "B": ["Bernard", "Benjamin", "Bruce"],
            "C": ["Charles", "Carl", "Christopher"],
            "D": ["David", "Daniel", "Donald"],
            "E": ["Edward", "Eugene", "Earl"],
            "F": ["Francis", "Frank", "Frederick"],
            "G": ["George", "Gerald", "Gordon"],
            "H": ["Henry", "Harold", "Howard"],
            "J": ["James", "John", "Joseph", "Jack"],
            "K": ["Kenneth", "Keith"],
            "L": ["Louis", "Lawrence", "Leonard", "Lee"],
            "M": ["Michael", "Martin", "Matthew"],
            "N": ["Norman", "Nelson"],
            "O": ["Oliver", "Oscar"],
            "P": ["Paul", "Peter", "Patrick"],
            "R": ["Robert", "Richard", "Raymond", "Ralph"],
            "S": ["Samuel", "Stephen", "Stanley"],
            "T": ["Thomas", "Theodore"],
            "W": ["William", "Walter", "Warren"],
        }
        options = middle_names.get(initial, [initial])
        return self.rng.choice(options) if options else initial

    def _create_assignment(
        self,
        component_id: str,
        regiment: Optional[str] = None,
        battalion: Optional[str] = None,
        company: Optional[str] = None,
    ) -> Assignment:
        """Create an assignment for a soldier."""
        comp = self.hierarchy.get_component(component_id)
        if not comp:
            raise ValueError(f"Unknown component: {component_id}")

        comp_type = comp.get("component_type", "")
        pattern = self.hierarchy.get_hierarchy_pattern(component_id)

        # Handle different component types
        if "air_force" in pattern:
            return self._create_aaf_assignment(component_id, comp)
        elif "combat_command" in pattern:
            return self._create_armored_assignment(component_id, comp, battalion, company)
        else:
            return self._create_infantry_assignment(
                component_id, comp, regiment, battalion, company
            )

    def _create_infantry_assignment(
        self,
        component_id: str,
        comp: Dict[str, Any],
        regiment: Optional[str],
        battalion: Optional[str],
        company: Optional[str],
    ) -> Assignment:
        """Create an infantry/airborne/mountain/marine assignment."""
        org = comp.get("organizational_structure", {})
        levels = org.get("levels", {})

        # Get available options
        regiments = levels.get("regiment", {}).get("designators", [])
        battalions = levels.get("battalion", {}).get("designators", [])
        companies = levels.get("company", {}).get("designators", [])

        # Select values
        if regiment is None and regiments:
            regiment = self.rng.choice(regiments)
        if battalion is None and battalions:
            battalion = self.rng.choice(battalions)
        if company is None and companies:
            company = self.rng.choice(companies)

        return Assignment(
            component_id=component_id,
            regiment=regiment,
            battalion=battalion,
            company=company,
        )

    def _create_armored_assignment(
        self,
        component_id: str,
        comp: Dict[str, Any],
        battalion: Optional[str],
        company: Optional[str],
    ) -> Assignment:
        """Create an armored division assignment."""
        org = comp.get("organizational_structure", {})
        levels = org.get("levels", {})

        combat_commands = levels.get("combat_command", {}).get("designators", [])
        battalions = levels.get("battalion", {}).get("designators", [])
        companies = levels.get("company", {}).get("designators", [])

        cc = self.rng.choice(combat_commands) if combat_commands else None
        if battalion is None and battalions:
            battalion = self.rng.choice(battalions)
        if company is None and companies:
            company = self.rng.choice(companies)

        return Assignment(
            component_id=component_id,
            combat_command=cc,
            battalion=battalion,
            company=company,
        )

    def _create_aaf_assignment(
        self,
        component_id: str,
        comp: Dict[str, Any],
    ) -> Assignment:
        """Create an Army Air Forces assignment."""
        org = comp.get("organizational_structure", {})
        levels = org.get("levels", {})

        bomb_groups = levels.get("bomb_group", {}).get("designators", [])
        squadrons = levels.get("squadron", {}).get("designators", [])

        bg = self.rng.choice(bomb_groups) if bomb_groups else None
        sq = self.rng.choice(squadrons) if squadrons else None

        return Assignment(
            component_id=component_id,
            bomb_group=bg,
            squadron=sq,
        )

    def create_soldiers_for_component(
        self,
        component_id: str,
        count: int,
        unit_concentration: float = 0.70,
    ) -> List[Soldier]:
        """
        Create multiple soldiers for a component with realistic clustering.

        Args:
            component_id: The component to assign soldiers to
            count: Number of soldiers to create
            unit_concentration: Rate of soldiers in same battalion (0-1)

        Returns:
            List of Soldier instances
        """
        soldiers = []

        # Determine primary unit for concentration
        primary_regiment = None
        primary_battalion = None

        for i in range(count):
            if i == 0 or self.rng.random() > unit_concentration:
                # New unit assignment
                soldier = self.create_soldier(component_id)
                if i == 0:
                    primary_regiment = soldier.assignment.regiment
                    primary_battalion = soldier.assignment.battalion
            else:
                # Same unit (concentrated)
                soldier = self.create_soldier(
                    component_id,
                    regiment=primary_regiment,
                    battalion=primary_battalion,
                )

            soldiers.append(soldier)

        return soldiers

    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        return {
            "total_soldiers_created": self._soldier_counter,
        }
