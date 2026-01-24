# Session Wrap-up Prompts

Copy and paste at end of session.

---

## For Opus GUI Sessions
```
I need to wrap up this session. Please generate the following artifacts:

1. **SESSION_STATE.md update** — formatted as a complete replacement for the file:
   - Active task (one sentence)
   - Current approach and key decisions made
   - Where I left off (specific next step)
   - Open questions remaining

2. **Extract for `.project_history/extracts/raw/`** — filename format YYYY-MM-DD_opus_[topic].md:
   - Key decisions made and rationale
   - Alternatives considered and why rejected
   - Implications for implementation
   - Any warnings or pitfalls identified

3. **Instruction file(s)** if we defined executable tasks — for `instructions/active/`:
   - Full spec per our discussion
   - Ready for Sonnet execution

Generate all three as copyable text blocks I can save directly.
```

---

## For Claude Code Sessions
```
Before we finish, update the project state:

1. Read current SESSION_STATE.md
2. Update it to reflect:
   - What we accomplished
   - Current state of the task
   - Next steps
3. Write the updated file to SESSION_STATE.md

Also note any issues or surprises we encountered.
```

---

## For End-of-Day Reconciliation (Sonnet)
```
I have these session extracts from today: [list files or paste content]

Create a daily reconciliation that:
1. Synthesizes the key decisions across sessions
2. Notes any tensions or open questions
3. Identifies what CURRENT.md files need updating
4. Lists concrete next steps

Format for `.project_history/extracts/daily/YYYY-MM-DD_[topic].md`
```
