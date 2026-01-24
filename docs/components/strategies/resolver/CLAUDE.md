# Resolver Strategy: Operational Warnings

These pitfalls are specific to the resolver strategy. Review before modifying resolver generation or execution.

## Resolver-Specific Pitfalls

- **Spurious pattern induction**: Heuristics reflect quirks of the sampled training records rather than stable evidence.

- **Over-generalization**: Patterns match across collision zones and fire on adjacent components.

- **Overfitting to injections**: Heuristics mirror injected reference data instead of record evidence.

- **Coverage gaps**: Resolver rules handle canonical formats but miss clerk variation and partial paths.

- **Internal inconsistency**: Generated patterns conflict or encode incompatible assumptions.

## Implications for Resolver Work

When building or modifying resolvers:
- Test patterns against collision pairs, not just single-component data
- Verify patterns fire on held-out data, not just training samples
- Check for rule conflicts in the assembled resolver JSON

## See Also

- Resolver design: `docs/components/strategies/resolver/CURRENT.md`
- Cross-strategy pitfalls: `docs/components/strategies/CLAUDE.md`
- Grounded inference policy: ADR-005
