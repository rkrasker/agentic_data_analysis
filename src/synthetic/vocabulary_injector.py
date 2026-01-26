"""
VocabularyInjector: Inject vocabulary terms into raw entries.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Clerk, Situation, VocabularyDensity


CLUTTER_RATES = {
    "sector_formal": 0.05,
    "sector_efficient": 0.08,
    "fleet_rushed": 0.12,
    "fleet_methodical": 0.08,
    "field_exhausted": 0.20,
    "field_medevac": 0.25,
    "field_minimal": 0.20,
    "transport_shuttle": 0.30,
    "processing_intake": 0.15,
    "defense_squadron": 0.18,
    "defense_operations": 0.22,
    "expeditionary_field": 0.22,
    "colonial_district": 0.10,
    "resource_facility": 0.12,
    "resource_processing": 0.15,
}

ARCHETYPE_TO_CLUTTER = {
    "transport_shuttle": "transport",
    "field_medevac": "medical",
    "processing_intake": "processing",
    "colonial_district": "processing",
    "resource_processing": "processing",
    "defense_operations": "operations",
    "defense_squadron": "operations",
    "fleet_rushed": "operations",
    "fleet_methodical": "operations",
}

SITUATIONAL_DENSITY = {
    VocabularyDensity.LOW: 0.15,
    VocabularyDensity.MEDIUM: 0.35,
    VocabularyDensity.HIGH: 0.55,
}

CONFOUNDER_RATE = 0.08


class VocabularyInjector:
    """Injects vocabulary terms into entry text based on three layers."""

    def __init__(
        self,
        vocabulary_path: Optional[Path] = None,
        random_seed: Optional[int] = None,
    ):
        self.rng = random.Random(random_seed)
        self.situational_terms: Dict[str, List[str]] = {}
        self.clutter_terms: Dict[str, List[str]] = {}
        self.confounder_terms: List[str] = []

        if vocabulary_path:
            self.load_vocabulary(vocabulary_path)

    def load_vocabulary(self, vocabulary_path: Path) -> None:
        """Load vocabulary from JSON file."""
        with open(vocabulary_path, "r") as f:
            data = json.load(f)

        self.situational_terms = data.get("situational", {})
        self.clutter_terms = data.get("clutter", {})

        confounders = data.get("confounders", {})
        combined: List[str] = []
        for values in confounders.values():
            combined.extend(values)
        self.confounder_terms = combined

    def inject_vocabulary(
        self,
        entry_text: str,
        clerk: Clerk,
        situation: Situation,
    ) -> Tuple[str, Dict[str, List[str]]]:
        """Inject vocabulary into an entry based on all three layers."""
        injected: Dict[str, List[str]] = {
            "situational": [],
            "clutter": [],
            "confounder": [],
        }

        result = entry_text

        situational_rate = SITUATIONAL_DENSITY.get(clerk.vocabulary_density, 0.35)
        if self.rng.random() < situational_rate:
            term = self._sample_situational(situation)
            if term:
                result = self._append_term(result, term)
                injected["situational"].append(term)

        clutter_rate = CLUTTER_RATES.get(clerk.archetype_id, 0.15)
        if self.rng.random() < clutter_rate:
            clutter_term = self._sample_clutter(clerk)
            if clutter_term:
                result = self._append_term(result, clutter_term)
                injected["clutter"].append(clutter_term)

                if self.rng.random() < CONFOUNDER_RATE:
                    confounder = self._sample_confounder()
                    if confounder:
                        result = self._append_term(result, confounder)
                        injected["confounder"].append(confounder)

        return result, injected

    def _sample_situational(self, situation: Situation) -> Optional[str]:
        """Sample a situational term for a situation."""
        pool = situation.vocabulary_pool.primary
        if not pool:
            pool = self.situational_terms.get(situation.situation_id, [])
        if not pool:
            return None
        return self.rng.choice(pool)

    def _sample_clutter(self, clerk: Clerk) -> Optional[str]:
        """Sample clutter terms for a clerk's context."""
        category = ARCHETYPE_TO_CLUTTER.get(clerk.archetype_id, "operations")
        pool = self.clutter_terms.get(category, [])
        if not pool:
            return None
        return self.rng.choice(pool)

    def _sample_confounder(self) -> Optional[str]:
        """Sample a confounder term."""
        if not self.confounder_terms:
            return None
        return self.rng.choice(self.confounder_terms)

    def _append_term(self, text: str, term: str) -> str:
        """Append a term to entry text with appropriate spacing."""
        if self.rng.random() < 0.3:
            return f"{text}  {term}"
        return f"{text} {term}"
