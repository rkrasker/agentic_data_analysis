"""
VocabularyInjector: Inject vocabulary terms into raw entries.

Three layers:
1. Situational vocabulary - Signal-bearing terms from the operation
2. Contextual clutter - Non-signal noise from clerk's environment
3. Confounders - Deliberately ambiguous terms resembling unit data
"""

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .models import Clerk, Situation, VocabularyDensity


# Clutter rates by archetype (from spec)
CLUTTER_RATES = {
    "hq_formal": 0.05,
    "hq_efficient": 0.08,
    "battalion_rushed": 0.12,
    "battalion_methodical": 0.08,
    "field_exhausted": 0.20,
    "field_medevac": 0.25,
    "transport_ship": 0.30,
    "transport_air": 0.20,
    "repldep_intake": 0.15,
    "aaf_squadron": 0.18,
    "aaf_operations": 0.22,
    "marine_fmf": 0.10,
    "marine_shipboard": 0.28,
}

# Situational vocabulary density by level
SITUATIONAL_DENSITY = {
    VocabularyDensity.LOW: 0.15,
    VocabularyDensity.MEDIUM: 0.35,
    VocabularyDensity.HIGH: 0.55,
}

# Confounder rate (8% of clutter entries include a confounder)
CONFOUNDER_RATE = 0.08


class VocabularyInjector:
    """
    Injects vocabulary terms into entry text based on three layers.

    Vocabulary is NOT randomly sampled - it appears based on:
    1. The source's assigned situation (signal)
    2. The clerk's working context (clutter)
    3. Deliberately ambiguous confounders
    """

    def __init__(
        self,
        vocabulary_path: Optional[Path] = None,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the injector.

        Args:
            vocabulary_path: Path to synthetic_vocabulary.json
            random_seed: Seed for reproducibility
        """
        self.rng = random.Random(random_seed)

        # Raw vocabulary data
        self.vocabulary: List[Dict[str, Any]] = []

        # Indexed by type and context
        self.clutter_by_context: Dict[str, List[Dict[str, Any]]] = {}
        self.confounders_by_context: Dict[str, List[Dict[str, Any]]] = {}

        # Frequency weights
        self.frequency_weights = {
            "common": 0.60,
            "uncommon": 0.30,
            "rare": 0.10,
        }

        if vocabulary_path:
            self.load_vocabulary(vocabulary_path)

    def load_vocabulary(self, vocabulary_path: Path) -> None:
        """Load vocabulary from JSON file."""
        with open(vocabulary_path, "r") as f:
            data = json.load(f)

        self.vocabulary = data.get("vocabulary", [])
        self.frequency_weights = data.get("frequency_weights", self.frequency_weights)

        # Index clutter and confounders by clerk context
        self._index_by_context()

    def _index_by_context(self) -> None:
        """Index clutter and confounders by clerk context."""
        self.clutter_by_context = {}
        self.confounders_by_context = {}

        for term in self.vocabulary:
            # Skip section markers
            if "_section" in term:
                continue

            term_type = term.get("term_type", "")
            clerk_contexts = term.get("clerk_context", [])

            if term_type == "clutter_code":
                for ctx in clerk_contexts:
                    if ctx not in self.clutter_by_context:
                        self.clutter_by_context[ctx] = []
                    self.clutter_by_context[ctx].append(term)

            elif term_type == "confounder":
                for ctx in clerk_contexts:
                    if ctx not in self.confounders_by_context:
                        self.confounders_by_context[ctx] = []
                    self.confounders_by_context[ctx].append(term)

    def _expand_template(self, term_data: Dict[str, Any]) -> str:
        """
        Expand a template term with random values.

        Templates use patterns like:
        - {N} - random number from N_range
        - {L} - random letter from L_values
        - {NN} - 2-digit number from NN_range
        - {NNN} - 3-digit number from NNN_range
        """
        term = term_data.get("term", "")

        if not term_data.get("template", False):
            return term

        # Replace {N} with number
        if "{N}" in term and "N_range" in term_data:
            n_min, n_max = term_data["N_range"]
            n_val = self.rng.randint(n_min, n_max)
            term = term.replace("{N}", str(n_val))

        # Replace {L} with letter
        if "{L}" in term and "L_values" in term_data:
            l_val = self.rng.choice(term_data["L_values"])
            term = term.replace("{L}", l_val)

        # Replace {NN} with 2-digit number
        if "{NN}" in term and "NN_range" in term_data:
            nn_min, nn_max = term_data["NN_range"]
            nn_val = self.rng.randint(nn_min, nn_max)
            term = term.replace("{NN}", str(nn_val))

        # Replace {NNN} with 3-digit number
        if "{NNN}" in term and "NNN_range" in term_data:
            nnn_min, nnn_max = term_data["NNN_range"]
            nnn_val = self.rng.randint(nnn_min, nnn_max)
            term = term.replace("{NNN}", str(nnn_val))

        # Handle combined {N}{L} pattern
        if re.search(r"\{N\}\{L\}", term_data.get("term", "")):
            if "N_range" in term_data and "L_values" in term_data:
                n_min, n_max = term_data["N_range"]
                n_val = self.rng.randint(n_min, n_max)
                l_val = self.rng.choice(term_data["L_values"])
                term = f"{n_val}{l_val}"

        return term

    def _select_weighted(
        self,
        terms: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Select a term weighted by frequency."""
        if not terms:
            return None

        weights = []
        for t in terms:
            freq = t.get("frequency", "common")
            weights.append(self.frequency_weights.get(freq, 0.5))

        total = sum(weights)
        if total == 0:
            return self.rng.choice(terms)

        weights = [w / total for w in weights]
        return self.rng.choices(terms, weights=weights)[0]

    def sample_clutter(
        self,
        clerk: Clerk,
        count: int = 1,
    ) -> List[str]:
        """
        Sample clutter terms for a clerk's context.

        Args:
            clerk: The clerk producing the entry
            count: Number of terms to sample

        Returns:
            List of expanded clutter terms
        """
        # Map archetype to context key
        context_key = clerk.archetype_id
        available = self.clutter_by_context.get(context_key, [])

        if not available:
            return []

        terms = []
        for _ in range(count):
            term_data = self._select_weighted(available)
            if term_data:
                expanded = self._expand_template(term_data)
                terms.append(expanded)

        return terms

    def sample_confounder(
        self,
        clerk: Clerk,
    ) -> Optional[str]:
        """
        Sample a confounder term for a clerk's context.

        Args:
            clerk: The clerk producing the entry

        Returns:
            An expanded confounder term, or None
        """
        context_key = clerk.archetype_id
        available = self.confounders_by_context.get(context_key, [])

        if not available:
            return None

        term_data = self._select_weighted(available)
        if term_data:
            return self._expand_template(term_data)

        return None

    def inject_vocabulary(
        self,
        entry_text: str,
        clerk: Clerk,
        situation: Situation,
        situational_terms: Optional[List[str]] = None,
    ) -> Tuple[str, Dict[str, List[str]]]:
        """
        Inject vocabulary into an entry based on all three layers.

        Args:
            entry_text: The base entry text (name, rank, unit)
            clerk: The clerk producing the entry
            situation: The source's assigned situation
            situational_terms: Pre-selected situational terms for consistency

        Returns:
            Tuple of (modified text, dict of injected terms by layer)
        """
        injected: Dict[str, List[str]] = {
            "situational": [],
            "clutter": [],
            "confounder": [],
        }

        result = entry_text

        # Layer 1: Situational vocabulary
        situational_rate = SITUATIONAL_DENSITY.get(
            clerk.vocabulary_density, 0.35
        )

        if self.rng.random() < situational_rate:
            if situational_terms:
                # Use pre-selected terms for source consistency
                term = self.rng.choice(situational_terms)
            else:
                # Sample from situation pool
                pool = (
                    situation.vocabulary_pool.primary +
                    situation.vocabulary_pool.secondary
                )
                if pool:
                    term = self.rng.choice(pool)
                else:
                    term = None

            if term:
                result = self._append_term(result, term)
                injected["situational"].append(term)

        # Layer 2: Contextual clutter
        clutter_rate = CLUTTER_RATES.get(clerk.archetype_id, 0.15)

        if self.rng.random() < clutter_rate:
            clutter_terms = self.sample_clutter(clerk, 1)
            if clutter_terms:
                clutter_term = clutter_terms[0]
                result = self._append_term(result, clutter_term)
                injected["clutter"].append(clutter_term)

                # Layer 3: Confounder (8% of clutter entries)
                if self.rng.random() < CONFOUNDER_RATE:
                    confounder = self.sample_confounder(clerk)
                    if confounder:
                        result = self._append_term(result, confounder)
                        injected["confounder"].append(confounder)

        return result, injected

    def _append_term(self, text: str, term: str) -> str:
        """Append a term to entry text with appropriate spacing."""
        # Sometimes add extra space for columnar effect
        if self.rng.random() < 0.3:
            return f"{text}  {term}"
        return f"{text} {term}"

    def select_source_vocabulary(
        self,
        situation: Situation,
        count: int = 3,
    ) -> List[str]:
        """
        Select vocabulary terms for a source (for within-source consistency).

        Once selected, these terms should be reused throughout the source.

        Args:
            situation: The source's assigned situation
            count: Number of terms to select

        Returns:
            List of vocabulary terms for the source
        """
        pool = (
            situation.vocabulary_pool.primary +
            situation.vocabulary_pool.secondary
        )

        if not pool:
            return []

        # Weight primary terms higher
        weights = []
        primary_set = set(situation.vocabulary_pool.primary)
        for term in pool:
            if term in primary_set:
                weights.append(2.0)
            else:
                weights.append(1.0)

        total = sum(weights)
        weights = [w / total for w in weights]

        count = min(count, len(pool))
        return self.rng.choices(pool, weights=weights, k=count)

    def get_contexts(self) -> List[str]:
        """Get all available clerk contexts."""
        contexts = set(self.clutter_by_context.keys())
        contexts.update(self.confounders_by_context.keys())
        return sorted(contexts)
