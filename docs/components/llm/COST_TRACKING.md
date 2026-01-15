# Cost Tracking System for Gemini API

This system tracks API costs, token usage, and execution metrics for resolver generation tasks.

## Features

- **Per-Phase Tracking**: Monitors each of the 8 phases separately
- **Token Estimation**: Estimates input/output tokens for cost calculation
- **Continuous Logging**: Real-time logs with timestamps
- **Cost Reports**: JSON reports with detailed breakdowns
- **Error Tracking**: Captures and logs API errors

## Files

- `src/utils/cost_tracker.py` - Core tracking module
- `generate_resolver.py` - Integrated with cost tracking
- `logs/` - Output directory for logs and reports

## Usage

### Normal Mode (with API calls)

```bash
python generate_resolver.py --component 82nd_airborne_division
```

This will create:
- `logs/resolver_82nd_airborne_division_YYYYMMDD_HHMMSS.log` - Detailed execution log
- `logs/resolver_82nd_airborne_division_YYYYMMDD_HHMMSS_cost.json` - Cost report

### Dry-Run Mode (no API calls, no costs)

```bash
python generate_resolver.py --component 82nd_airborne_division --dry-run
```

No log files are created in dry-run mode.

## Pricing Reference

Current Gemini API pricing (per 1 million tokens):

| Model | Input | Output |
|-------|--------|--------|
| gemini-2.5-pro | $1.25 | $5.00 |
| gemini-2.0-flash | $0.10 | $0.40 |
| gemini-1.5-pro | $1.25 | $5.00 |
| gemini-1.5-flash | $0.075 | $0.30 |

## Log File Format

### Execution Log (.log)

```
================================================================================
RESOLVER GENERATION LOG
Task: resolver_82nd_airborne_division
Model: gemini-2.5-pro
Started: 2026-01-11 14:30:00
================================================================================

TASK PARAMETERS:
{
  "component_id": "82nd_airborne_division",
  "model": "gemini-2.5-pro",
  "validation_records": 700,
  "raw_records": 2100
}

[14:30:01] PHASE START: phase1_structural_rules
[14:30:02] PHASE END: phase1_structural_rules - completed
  Duration: 1.23s
  API Calls: 0
  Input Tokens: 0
  Output Tokens: 0
  Cost: $0.0000

[14:30:02] PHASE START: phase4_pattern_discovery
[14:30:03] API CALL #1 (phase4_pattern_discovery)
  Input: 2,450 tokens | Output: 820 tokens
  Cost: $0.0071
  Prompt: Analyze military records from 82nd Airborne Division using CROSS-RECORD CONTEXT...
[14:30:04] PHASE END: phase4_pattern_discovery - completed
  Duration: 2.15s
  API Calls: 1
  Input Tokens: 2,450
  Output Tokens: 820
  Cost: $0.0071

...

================================================================================
EXECUTION SUMMARY
================================================================================
Total Duration: 125.45s (2.09 minutes)
Total API Calls: 4
Total Input Tokens: 8,920
Total Output Tokens: 3,105
Total Cost: $0.0267

PHASE BREAKDOWN:
  phase1_structural_rules:
    Duration: 1.23s
    API Calls: 0
    Tokens: 0 in / 0 out
    Cost: $0.0000
  phase4_pattern_discovery:
    Duration: 2.15s
    API Calls: 1
    Tokens: 2,450 in / 820 out
    Cost: $0.0071
  phase5_exclusion_mining:
    Duration: 1.89s
    API Calls: 1
    Tokens: 2,100 in / 750 out
    Cost: $0.0064
  ...

Log file: logs/resolver_82nd_airborne_division_20260111_143000.log
Cost report: logs/resolver_82nd_airborne_division_20260111_143000_cost.json
```

### Cost Report (.json)

```json
{
  "task_name": "resolver_82nd_airborne_division",
  "model": "gemini-2.5-pro",
  "start_time": "2026-01-11T14:30:00",
  "end_time": "2026-01-11T14:32:05",
  "duration_seconds": 125.45,
  "parameters": {
    "component_id": "82nd_airborne_division",
    "model": "gemini-2.5-pro",
    "dry_run": false,
    "validation_records": 700,
    "raw_records": 2100
  },
  "totals": {
    "api_calls": 4,
    "input_tokens": 8920,
    "output_tokens": 3105,
    "total_tokens": 12025,
    "cost_usd": 0.0267
  },
  "phases": {
    "phase1_structural_rules": {
      "start_time": 1736630401.234,
      "input_tokens": 0,
      "output_tokens": 0,
      "api_calls": 0,
      "status": "completed",
      "end_time": 1736630402.464,
      "duration": 1.23,
      "cost": 0.0
    },
    "phase4_pattern_discovery": {
      "start_time": 1736630402.5,
      "input_tokens": 2450,
      "output_tokens": 820,
      "api_calls": 1,
      "status": "completed",
      "end_time": 1736630404.65,
      "duration": 2.15,
      "cost": 0.0071
    }
  },
  "errors": [],
  "pricing": {
    "input": 1.25,
    "output": 5.0
  }
}
```

## API Call Tracking

Each API call is logged with:
- Timestamp
- Phase name
- Input/output token counts
- Estimated cost
- Prompt preview (first 100-200 characters)
- Error message (if failed)

## Cost Estimation

Token counts are **estimated** using the formula: `tokens ≈ characters / 4`

This is a rough approximation. Actual token counts may vary. For precise tracking, consider using the official Gemini API token counting endpoints.

## Error Handling

- Rate limit errors are logged with retry attempts
- API failures are tracked per phase
- Errors don't stop execution log finalization

## Interpreting Results

### High-Cost Phases
Phases 4-7 use LLM calls and will have non-zero costs:
- **Phase 4** (Pattern Discovery): Typically 2,000-3,000 input tokens
- **Phase 5** (Exclusion Mining): Typically 1,500-2,500 input tokens
- **Phase 6** (Vocabulary): Typically 2,000-3,000 input tokens
- **Phase 7** (Differentiators): Typically 2,000-3,000 input tokens

### Expected Total Cost Per Resolver
With Gemini 2.5 Pro:
- **Small component** (10-50 soldiers): $0.02-0.04
- **Medium component** (50-200 soldiers): $0.04-0.08
- **Large component** (200+ soldiers): $0.08-0.15

### Optimization Tips
1. Use `--dry-run` for testing without costs
2. Use cheaper models (gemini-2.0-flash) for experimentation
3. Leverage resumable state - phases are saved and won't re-run
4. Clear state only when necessary with `--clear-state`

## Example Commands

```bash
# Generate with cost tracking
python generate_resolver.py --component 1st_infantry_division

# Use cheaper model
python generate_resolver.py --component 1st_infantry_division --model gemini-2.0-flash

# Resume from saved state (no API calls for completed phases)
python generate_resolver.py --component 1st_infantry_division

# Start fresh (will re-run all phases and incur costs)
python generate_resolver.py --component 1st_infantry_division --clear-state

# Test without API costs
python generate_resolver.py --component 1st_infantry_division --dry-run
```

## Viewing Results

After generation, check:
```bash
# View latest log
cat logs/resolver_*_*.log | tail -50

# View cost summary
cat logs/resolver_*_cost.json | jq '.totals'

# Total costs across all runs
cat logs/*_cost.json | jq '.totals.cost_usd' | awk '{sum+=$1} END {print "Total: $"sum}'
```

## Troubleshooting

**No log files created?**
- Check if running in `--dry-run` mode (logs disabled)
- Verify `logs/` directory exists and is writable

**Costs seem high?**
- Check which model you're using (`gemini-2.5-pro` is most expensive)
- Review token counts in the log to see which prompts are large
- Consider using `gemini-2.0-flash` for development

**Missing phases in log?**
- Phases completed in previous runs won't be re-tracked
- Use `--clear-state` to start fresh
