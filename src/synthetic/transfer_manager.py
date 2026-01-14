"""
TransferManager: Generate and track unit transfers for soldiers.

25% of soldiers have a transfer, creating disambiguation challenges
where the same soldier legitimately appears with different unit
assignments across sources.
"""

import random
from typing import Dict, List, Optional, Any, Tuple

from .models import Soldier, Assignment, Transfer, TransferType


# Transfer type distribution (from spec)
TRANSFER_TYPE_WEIGHTS = {
    TransferType.COMPANY: 0.50,      # Same battalion, different company
    TransferType.BATTALION: 0.30,    # Same regiment, different battalion
    TransferType.REGIMENT: 0.15,     # Same division, different regiment
    TransferType.DIVISION: 0.05,     # Different division
}

# Soldier transfer rate
SOLDIER_TRANSFER_RATE = 0.25

# Company letters for transfers
COMPANY_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M"]


class TransferManager:
    """
    Manages unit transfers for soldiers.

    Transfers create the hardest disambiguation cases: the same soldier
    legitimately appears with different unit assignments across sources.
    """

    def __init__(
        self,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the manager.

        Args:
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)
        self.transfers: Dict[str, Transfer] = {}

        # Track transfer statistics
        self.transfer_counts: Dict[TransferType, int] = {
            t: 0 for t in TransferType
        }

    def should_transfer(self) -> bool:
        """Determine if a soldier should have a transfer."""
        return self.rng.random() < SOLDIER_TRANSFER_RATE

    def select_transfer_type(self) -> TransferType:
        """Select a transfer type based on distribution."""
        types = list(TRANSFER_TYPE_WEIGHTS.keys())
        weights = [TRANSFER_TYPE_WEIGHTS[t] for t in types]
        return self.rng.choices(types, weights=weights)[0]

    def generate_transfer(
        self,
        soldier: Soldier,
        available_regiments: Optional[List[str]] = None,
        available_divisions: Optional[List[str]] = None,
    ) -> Optional[Transfer]:
        """
        Generate a transfer for a soldier.

        Args:
            soldier: The soldier to transfer
            available_regiments: Optional list of regiment IDs for regiment-level transfers
            available_divisions: Optional list of division component_ids for division-level transfers

        Returns:
            Transfer object if transfer generated, None otherwise
        """
        if not self.should_transfer():
            return None

        transfer_type = self.select_transfer_type()
        original = soldier.assignment

        # Generate new assignment based on transfer type
        new_assignment = self._generate_new_assignment(
            transfer_type,
            original,
            available_regiments,
            available_divisions,
        )

        if new_assignment is None:
            return None

        transfer = Transfer(
            soldier_id=soldier.primary_id,
            transfer_type=transfer_type,
            original_assignment=original,
            new_assignment=new_assignment,
        )

        # Update soldier
        soldier.original_assignment = original
        soldier.assignment = new_assignment
        soldier.has_transfer = True

        # Track transfer
        self.transfers[soldier.primary_id] = transfer
        self.transfer_counts[transfer_type] += 1

        return transfer

    def _generate_new_assignment(
        self,
        transfer_type: TransferType,
        original: Assignment,
        available_regiments: Optional[List[str]] = None,
        available_divisions: Optional[List[str]] = None,
    ) -> Optional[Assignment]:
        """Generate a new assignment based on transfer type."""

        if transfer_type == TransferType.COMPANY:
            return self._transfer_company(original)

        elif transfer_type == TransferType.BATTALION:
            return self._transfer_battalion(original)

        elif transfer_type == TransferType.REGIMENT:
            return self._transfer_regiment(original, available_regiments)

        elif transfer_type == TransferType.DIVISION:
            return self._transfer_division(original, available_divisions)

        return None

    def _transfer_company(self, original: Assignment) -> Assignment:
        """Transfer to different company in same battalion."""
        # Get a different company letter
        current_company = original.company
        available = [c for c in COMPANY_LETTERS if c != current_company]

        if not available:
            available = COMPANY_LETTERS

        new_company = self.rng.choice(available)

        return Assignment(
            component_id=original.component_id,
            regiment=original.regiment,
            battalion=original.battalion,
            company=new_company,
            combat_command=original.combat_command,
            bomb_group=original.bomb_group,
            squadron=original.squadron,
        )

    def _transfer_battalion(self, original: Assignment) -> Assignment:
        """Transfer to different battalion in same regiment."""
        current_bn = original.battalion
        battalions = ["1st", "2nd", "3rd"]

        available = [b for b in battalions if b != current_bn]
        if not available:
            available = battalions

        new_bn = self.rng.choice(available)

        # Also change company (realistic)
        new_company = self.rng.choice(COMPANY_LETTERS)

        return Assignment(
            component_id=original.component_id,
            regiment=original.regiment,
            battalion=new_bn,
            company=new_company,
            combat_command=original.combat_command,
            bomb_group=original.bomb_group,
            squadron=original.squadron,
        )

    def _transfer_regiment(
        self,
        original: Assignment,
        available_regiments: Optional[List[str]] = None,
    ) -> Assignment:
        """Transfer to different regiment in same division."""
        current_reg = original.regiment

        # Handle units without regiments (AAF, etc.) - fall back to battalion transfer
        if current_reg is None:
            return self._transfer_battalion(original)

        if available_regiments:
            candidates = [r for r in available_regiments if r != current_reg]
            if candidates:
                new_reg = self.rng.choice(candidates)
            else:
                # Fallback: modify regiment number
                new_reg = self._modify_regiment_number(current_reg)
        else:
            new_reg = self._modify_regiment_number(current_reg)

        # New battalion and company
        new_bn = self.rng.choice(["1st", "2nd", "3rd"])
        new_company = self.rng.choice(COMPANY_LETTERS)

        return Assignment(
            component_id=original.component_id,
            regiment=new_reg,
            battalion=new_bn,
            company=new_company,
            combat_command=original.combat_command,
            bomb_group=original.bomb_group,
            squadron=original.squadron,
        )

    def _modify_regiment_number(self, regiment: str) -> str:
        """Create a different regiment number."""
        import re
        match = re.search(r'(\d+)', regiment)
        if match:
            num = int(match.group(1))
            # Add or subtract to get different regiment
            offset = self.rng.choice([-2, -1, 1, 2])
            new_num = max(1, num + offset)
            return re.sub(r'\d+', str(new_num), regiment)
        return regiment

    def _transfer_division(
        self,
        original: Assignment,
        available_divisions: Optional[List[str]] = None,
    ) -> Assignment:
        """Transfer to different division via replacement depot."""
        current_div = original.component_id

        if available_divisions:
            candidates = [d for d in available_divisions if d != current_div]
            if candidates:
                new_div = self.rng.choice(candidates)
            else:
                new_div = current_div  # Can't transfer if no alternatives
        else:
            new_div = current_div

        # Completely new unit structure in new division
        new_bn = self.rng.choice(["1st", "2nd", "3rd"])
        new_company = self.rng.choice(COMPANY_LETTERS)

        return Assignment(
            component_id=new_div,
            regiment=None,  # Will need to be filled in based on hierarchy
            battalion=new_bn,
            company=new_company,
            combat_command=None,
            bomb_group=None,
            squadron=None,
        )

    def apply_transfers_to_soldiers(
        self,
        soldiers: List[Soldier],
        available_regiments: Optional[Dict[str, List[str]]] = None,
        available_divisions: Optional[List[str]] = None,
    ) -> List[Transfer]:
        """
        Apply transfers to a list of soldiers.

        Args:
            soldiers: List of soldiers to potentially transfer
            available_regiments: Dict mapping component_id to regiment list
            available_divisions: List of division component_ids

        Returns:
            List of generated transfers
        """
        transfers = []

        for soldier in soldiers:
            # Get regiments for this soldier's component
            regs = None
            if available_regiments:
                regs = available_regiments.get(soldier.assignment.component_id, [])

            transfer = self.generate_transfer(
                soldier,
                available_regiments=regs,
                available_divisions=available_divisions,
            )

            if transfer:
                transfers.append(transfer)

        return transfers

    def get_transfer(self, soldier_id: str) -> Optional[Transfer]:
        """Get a transfer by soldier ID."""
        return self.transfers.get(soldier_id)

    def get_transferred_soldiers(self) -> List[str]:
        """Get list of soldier IDs with transfers."""
        return list(self.transfers.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get transfer statistics."""
        total = sum(self.transfer_counts.values())
        return {
            "total_transfers": total,
            "by_type": {t.value: c for t, c in self.transfer_counts.items()},
            "type_distribution": {
                t.value: c / max(total, 1)
                for t, c in self.transfer_counts.items()
            },
        }

    def to_records(self) -> List[Dict[str, Any]]:
        """
        Convert transfers to records for parquet export.

        Returns:
            List of dicts suitable for DataFrame creation
        """
        records = []
        for soldier_id, transfer in self.transfers.items():
            record = {
                "soldier_id": soldier_id,
                "transfer_type": transfer.transfer_type.value,
                # Original assignment
                "original_component_id": transfer.original_assignment.component_id,
                "original_regiment": transfer.original_assignment.regiment,
                "original_battalion": transfer.original_assignment.battalion,
                "original_company": transfer.original_assignment.company,
                # New assignment
                "new_component_id": transfer.new_assignment.component_id,
                "new_regiment": transfer.new_assignment.regiment,
                "new_battalion": transfer.new_assignment.battalion,
                "new_company": transfer.new_assignment.company,
            }
            records.append(record)
        return records
