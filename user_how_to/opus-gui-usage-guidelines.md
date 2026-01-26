# Opus GUI Usage Guidelines

A reference for effective conceptual work in the Claude GUI, designed to complement execution work in Claude Code.

---

## Why Use the GUI for Conceptual Work?

### Context Window Efficiency

Claude Code's context window accumulates operational noise: file contents, tool call results, directory listings, error traces. This is essential for execution but wasteful for reasoning.

In the GUI, your entire context budget goes toward the actual problem—the tradeoffs, constraints, and design considerations you're reasoning about.

### Behavioral Orientation

Claude Code puts the agent in **action mode**. Its default is "what can I do next?" Even during design discussions, it tends to reach for files or propose implementation.

The GUI puts the agent in **dialogue mode**. You can explore, reconsider, back up, and reframe—without the agent having already modified code in a direction you're now questioning.

### The Handoff Model

- **GUI (Opus)**: Generate high-quality specifications through dialogue → output is instruction files, decision records, architecture updates
- **Claude Code (Sonnet)**: Execute those specifications → output is working code

Each model and interface is used for what it does best.

---

## Before the Session: Loading Context

### The Core Problem

You can't reference files directly in the GUI. If you miss a key constraint, the reasoning may be flawed. Mitigation requires discipline.

### Strategies

**Pre-built context packets**

For each major area of your codebase, maintain a curated bundle: key interfaces, constraints, dependencies, current state. Not full code—just what's needed to reason about that area.

When you sit down for an Opus session about component X, load the component X packet.

Maintenance discipline: After implementation work, task Sonnet with updating the relevant context packet.

**Structured problem framing**

Before engaging Opus, write yourself a brief problem statement:

- What does this touch?
- What are the boundaries?
- What existing decisions constrain this?

If you can't answer "what does this touch?" clearly, do exploration in Claude Code first (with Sonnet) before the design session.

**Let Opus probe for gaps**

Open with: "Before we go deep on this, what context would you want to know about? What questions would help you understand the constraints?"

If your answer to any question is "I'm not sure"—that's your cue to go get that information.

**Accept iterative loading**

You won't always get it right upfront. Mid-conversation, if you realize a dependency matters, pause, pull the relevant snippet, paste it in. The context cost is real but manageable for occasional additions.

---

## During the Session: Working Effectively

### Session Structure

**Opening** (5-10% of session)
- State the specific problem or decision
- Share what you've already considered
- Name the constraints
- Specify what output you need (instruction file? architecture decision? clarification?)

**Core work** (60-70% of session)
- Dense, focused exchange
- When you reach a decision, note it explicitly
- Don't let the session drift—Opus time is expensive

**Extraction** (20-30% of session)
- Shift toward output generation
- Request instruction files, decision summaries, documentation updates
- Don't start new threads of discussion

### Context Window Checkpoints

| Context Used | Action |
|--------------|--------|
| ~50% | Check if you have what you need. If the core problem is solved, start extracting. |
| ~70% | Actively shift toward output generation. |
| ~85% | Wrap up. Get final artifacts. No new threads. |

### Useful Prompts

- "Before we go deep, what context would help you reason about this?"
- "I'm deciding between A and B. Here are the tradeoffs I see..."
- "Given what we've discussed, what should the instruction file say?"
- "What from this conversation should persist for future reference?"
- "Summarize the key decisions and their rationale."

---

## After the Session: Capturing Reasoning

### The Problem

Reasoning doesn't preserve itself. A week later, you (or Sonnet) will hit the same question with no record of why you decided what you decided.

### Output Types

**Instruction files** (for Sonnet execution)

What to do, but also:
- Context/rationale section explaining the why
- Anti-patterns: "Don't do Y, even though it seems simpler, because Z"
- Decision boundaries: "If you encounter X, that's outside this spec—flag it"

**Decision records** (for future reference)

Separate from instruction files. Captures:
- What problem we were solving
- What options we considered
- Why we chose this approach
- What we explicitly decided NOT to do and why
- Edge cases discussed and how they should be handled

Lighter than a full transcript, denser than an instruction. This is what Sonnet can actually consume when it needs to understand intent.

**Raw transcripts** (archival)

Export the conversation. Save to `.project_history/extracts/raw/` or equivalent.

Useful for reconstruction, but not a primary reference—too long for agents to read.

**Documentation updates**

Some sessions should result in updates to:
- Component CURRENT.md files
- Architecture decision logs
- Context packets (for future sessions)

### The Wrap-Up Discipline

Every Opus session should end with explicit extraction:

> "What from this conversation needs to persist, and in what form?"

Don't end with just mental clarity. If nothing is written down, the reasoning is lost.

---

## When to Bend the Rules

The GUI-for-conceptual-work recommendation isn't absolute.

**Use Claude Code if:**
- The confusion is about what the code does (not what to do with it)
- You need the agent to actually read and trace through files
- The exploration is "help me understand this codebase" rather than "help me decide what to build"

**Use GUI if:**
- The question is about approach, architecture, or tradeoffs
- You're deciding between options
- You need to reason about something before implementing
- You want to avoid premature implementation

**The test:** Is the confusion about the code itself, or about what to do with it?

---

## Quick Reference Checklist

### Before Session
- [ ] Problem statement written (what does this touch? what constrains it?)
- [ ] Relevant context packet loaded
- [ ] Specific questions formulated (not just "help me with X")

### During Session
- [ ] Opened with problem, constraints, and desired output
- [ ] Keeping discussion focused (not drifting)
- [ ] Monitoring context usage
- [ ] Shifting to extraction by 70% context

### After Session
- [ ] Instruction file generated (if execution needed)
- [ ] Decision record created (if significant decisions made)
- [ ] Documentation updates identified
- [ ] Raw transcript exported (if archival needed)
- [ ] Context packet update queued (if relevant)

---

## File Locations Reference

| Artifact Type | Location |
|---------------|----------|
| Active instruction files | `instructions/active/` |
| Completed instructions | `instructions/completed/` |
| Decision records | `decisions/` or within component docs |
| Raw transcripts | `.project_history/extracts/raw/` |
| Context packets | `context/` or `docs/context-packets/` |
| Component state | `[component]/CURRENT.md` |
| Session state | `SESSION_STATE.md` |

Adapt these paths to your project structure.
