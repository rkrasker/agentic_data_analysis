# Code Style Preferences

This project favors explicit, readable code over architectural elegance.

## Core Principles

**Prefer functions over classes** for stateless operations. Only introduce a class when you need to manage state across multiple method calls.

**No premature abstraction.** Build for current requirements. "Future flexibility" that isn't needed now is complexity that costs now.

**Flat is better than nested; simple is better than clever.** If you can accomplish something with straightforward code, do that.

## Specific Guidance

### When to Use Classes

✓ Use a class when:
- Managing state across multiple method calls
- Implementing a defined interface (e.g., BaseStrategy)
- The object has a clear lifecycle (creation → use → cleanup)

✗ Don't use a class when:
- A function with parameters would work
- The "class" would have only `__init__` and one method
- You're wrapping a single operation

### What to Avoid

- **Factory patterns** unless construction logic is genuinely complex
- **Abstract base classes** with only one implementation
- **Getter/setter methods** when direct attribute access works
- **Configuration objects** for things that could be function parameters
- **Inheritance hierarchies** when composition (or nothing) would work

### Patterns That Fit This Project

- **Dataclasses** for structured data (already used throughout)
- **Module-level functions** for stateless operations
- **Simple classes** for stateful components with clear responsibilities
- **Dictionary/DataFrame returns** over custom container classes

## The Test

Before adding structure, ask: "Does this structure solve a problem I have now, or a problem I imagine having later?"

If later → don't add it. We can refactor when the need is real.

## Context

This guidance exists because LLM coding agents tend toward over-engineering. When in doubt, choose the simpler implementation.
