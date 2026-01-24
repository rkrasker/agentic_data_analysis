# Strategy Development: Operational Warnings

These pitfalls apply across all LLM-based strategies. Review before designing or modifying any strategy.

## Cross-Strategy LLM Pitfalls

- **Training prior leakage**: The model uses innate training data or general military knowledge instead of only provided data.

- **State over-splitting**: The model invents multiple states when a single post should explain the records.

- **State under-splitting**: Distinct posts are merged into one state because the model over-generalizes.

- **Order anchoring**: Early records or early batches lock the model into a wrong state count or grouping.

- **Drift across batches**: Successive batches shift interpretation even when evidence is similar.

- **Premature convergence**: The model stops revising candidate meanings once a grouping seems plausible.

- **Scaffolded hallucination**: Overly explicit prompting induces invented steps or unjustified inferences.

## Implications for Strategy Design

When designing prompts or evaluation criteria, explicitly test for these failure modes. A strategy that works on easy cases may fail via these pitfalls on harder cases.

## See Also

- Individual strategy designs: `docs/components/strategies/[name]/CURRENT.md`
- Strategy comparison: `docs/components/strategies/_comparison/CURRENT.md`
- Resolver-specific pitfalls: `docs/components/strategies/resolver/CLAUDE.md`
