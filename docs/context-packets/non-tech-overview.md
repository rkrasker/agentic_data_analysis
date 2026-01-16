# Project Overview (Non-Technical)

## What this project does

This project is about turning scattered historical records into clear, reliable unit
assignments for each soldier. The records are messy and inconsistent, so the goal is to
combine many lines for the same person and make the best overall judgment.

## What exists today

- A way to create realistic practice data, along with the correct answers for checking
  accuracy.
- A first pass that pulls out obvious clues like unit words, letters, and numbers.
- A standard format for storing records so later steps can work consistently.
- A test framework that compares predictions against the known answers.
- Tools for keeping track of how much model usage costs.
- Safety protections for running experimental code.

## What is not built yet

- The main “decision-making” methods that actually produce final assignments.
- The full system that groups records into the right buckets for those methods.
- A complete end‑to‑end run that ties all parts together.

## Key decisions so far (and why)

- **Use the original text as the main source.** The raw records are too messy for
  simple extraction to be enough.
- **Use simple pattern matching only as a helper.** It finds obvious clues quickly,
  but it cannot resolve meaning by itself.
- **Make the practice data feel human.** Real clerks repeat habits and make consistent
  kinds of mistakes, so the practice data mimics that.
- **Treat transfers as valid history.** A soldier can correctly appear under different
  units at different times, so the system must allow that.
- **Keep learning separate from testing.** The system must not “see the answers” while
  it is being evaluated, otherwise the results would be misleading.

## Current focus

The next steps are to finish the grouping process and build a baseline method that can
produce the first full set of assignments.
