# Synthetic Data Concepts

## Purpose
This synthetic dataset is designed to look like WWII-era clerical records while
preserving a reliable underlying truth. It supports experiments in disambiguation
and consolidation by mixing realistic ambiguity with consistent signal.

## What It Simulates
- Human clerks writing manifests and lists under varying conditions.
- Operational situations that shape the vocabulary used (e.g., locations,
  operations, equipment).
- Archival artifacts: inconsistent formatting, shorthand, and occasional errors.
- Transfers between units, creating legitimate changes in a soldier's unit data.
- Overlapping unit names across different divisions (the same number can refer
  to different units depending on context).

## How It Is Constructed (Conceptual)
1. **Truth layer (ground reality):**
   Each soldier has a canonical identity and unit assignment. This is the
   reference truth used for validation.

2. **Sources and clerks (document producers):**
   Records are generated in batches called sources, each produced by a single
   clerk. Clerks are modeled as persistent characters with stable habits.

3. **Situations (context):**
   Each source is tied to one operational situation that influences vocabulary
   across all entries in that source.

4. **Rendering (how truth becomes text):**
   The truth is rendered into raw text with the clerk's fixed formatting habits,
   plus context-specific vocabulary and controlled imperfections.

## Key Behavioral Features
- **Within-source consistency:** Most entries in a single source are formatted
  identically, reflecting real clerical habits.
- **Vocabulary layers:**
  - **Situational terms** provide signal tied to the operation or theater.
  - **Contextual clutter** adds non-signal noise from the clerk's environment.
  - **Confounders** resemble unit data but are not, forcing contextual reasoning.
- **Transfers:** A significant fraction of soldiers legitimately appear under
  different units, creating hard disambiguation cases.
- **Overlapping unit names:** Some unit names look identical across different
  divisions. The text includes other clues (like location terms and clerk
  context) to tell them apart, just like real records.

## Intended Conditions for Evaluation
- Ambiguity that cannot be resolved with a single feature or simple pattern.
- Signal that is present but mixed with realistic noise.
- Multi-entry reasoning required to determine consistent unit assignments.

## Outputs
- **Raw entries:** Text lines that resemble historical documents.
- **Validation truth:** Canonical identities and unit assignments.
- **Unit changes:** Explicit records of legitimate transfers.
