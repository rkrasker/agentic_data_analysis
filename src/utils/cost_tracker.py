"""
Cost Tracker for LLM API Calls
Tracks token usage, costs, and logs execution details for resolver generation.

Supports multiple providers: Gemini, Claude, OpenAI.
Pricing is managed centrally in src/utils/llm/config.py
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import threading


def _get_pricing() -> Dict[str, Dict[str, float]]:
    """
    Get pricing from the LLM config module.

    Returns dict mapping model_name -> {"input": price, "output": price}
    """
    try:
        from .llm.config import MODEL_REGISTRY
        return {
            name: {
                "input": config.input_price_per_million,
                "output": config.output_price_per_million,
            }
            for name, config in MODEL_REGISTRY.items()
        }
    except ImportError:
        # Fallback if llm module not available
        return {
            "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
            "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
            "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
            "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
            "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
            "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        }


# Lazy-loaded pricing (populated on first use)
PRICING: Optional[Dict[str, Dict[str, float]]] = None


def get_pricing() -> Dict[str, Dict[str, float]]:
    """Get pricing dict, loading from config if needed."""
    global PRICING
    if PRICING is None:
        PRICING = _get_pricing()
    return PRICING


class CostTracker:
    """Tracks API costs and execution metrics for a single task."""

    def __init__(self, task_name: str, model_name: str, log_dir: str = "logs"):
        self.task_name = task_name
        self.model_name = model_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Initialize tracking
        self.start_time = time.time()
        self.phases = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
        self.errors = []
        self.parameters = {}

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{task_name}_{timestamp}.log"
        self.cost_file = self.log_dir / f"{task_name}_{timestamp}_cost.json"

        # Thread lock for concurrent writes
        self._lock = threading.Lock()

        self._write_header()

    def _write_header(self):
        """Write log header with task info."""
        with open(self.log_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"RESOLVER GENERATION LOG\n")
            f.write(f"Task: {self.task_name}\n")
            f.write(f"Model: {self.model_name}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")

    def set_parameters(self, params: Dict[str, Any]):
        """Set task parameters for logging."""
        with self._lock:
            self.parameters.update(params)
            self._append_log(f"\nTASK PARAMETERS:\n{json.dumps(params, indent=2)}\n")

    def start_phase(self, phase_name: str):
        """Start tracking a phase."""
        with self._lock:
            self.phases[phase_name] = {
                "start_time": time.time(),
                "input_tokens": 0,
                "output_tokens": 0,
                "api_calls": 0,
                "status": "running"
            }
            self._append_log(f"\n[{self._timestamp()}] PHASE START: {phase_name}\n")

    def end_phase(self, phase_name: str, status: str = "completed"):
        """End tracking a phase."""
        with self._lock:
            if phase_name not in self.phases:
                return

            phase = self.phases[phase_name]
            phase["end_time"] = time.time()
            phase["duration"] = phase["end_time"] - phase["start_time"]
            phase["status"] = status

            cost = self._calculate_cost(
                phase["input_tokens"],
                phase["output_tokens"]
            )
            phase["cost"] = cost

            self._append_log(
                f"[{self._timestamp()}] PHASE END: {phase_name} - {status}\n"
                f"  Duration: {phase['duration']:.2f}s\n"
                f"  API Calls: {phase['api_calls']}\n"
                f"  Input Tokens: {phase['input_tokens']:,}\n"
                f"  Output Tokens: {phase['output_tokens']:,}\n"
                f"  Cost: ${cost:.4f}\n"
            )

    def record_api_call(self, phase_name: str, input_tokens: int, output_tokens: int,
                       prompt_preview: Optional[str] = None, error: Optional[str] = None):
        """Record an API call with token counts."""
        with self._lock:
            self.api_calls += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            if phase_name in self.phases:
                self.phases[phase_name]["api_calls"] += 1
                self.phases[phase_name]["input_tokens"] += input_tokens
                self.phases[phase_name]["output_tokens"] += output_tokens

            log_entry = (
                f"[{self._timestamp()}] API CALL #{self.api_calls} ({phase_name})\n"
                f"  Input: {input_tokens:,} tokens | Output: {output_tokens:,} tokens\n"
                f"  Cost: ${self._calculate_cost(input_tokens, output_tokens):.4f}\n"
            )

            if prompt_preview:
                preview = prompt_preview[:200].replace('\n', ' ')
                log_entry += f"  Prompt: {preview}...\n"

            if error:
                self.errors.append({"phase": phase_name, "error": error, "time": self._timestamp()})
                log_entry += f"  ERROR: {error}\n"

            self._append_log(log_entry)

    def record_event(self, event: str, details: Optional[str] = None):
        """Record a general event."""
        with self._lock:
            log_entry = f"[{self._timestamp()}] {event}\n"
            if details:
                log_entry += f"  {details}\n"
            self._append_log(log_entry)

    def finalize(self):
        """Finalize the tracking and write summary."""
        with self._lock:
            end_time = time.time()
            total_duration = end_time - self.start_time
            total_cost = self._calculate_cost(self.total_input_tokens, self.total_output_tokens)

            # Write summary to log
            summary = f"\n{'='*80}\n"
            summary += "EXECUTION SUMMARY\n"
            summary += f"{'='*80}\n"
            summary += f"Total Duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)\n"
            summary += f"Total API Calls: {self.api_calls}\n"
            summary += f"Total Input Tokens: {self.total_input_tokens:,}\n"
            summary += f"Total Output Tokens: {self.total_output_tokens:,}\n"
            summary += f"Total Cost: ${total_cost:.4f}\n"
            summary += f"\nPHASE BREAKDOWN:\n"

            for phase_name, phase in self.phases.items():
                if "duration" in phase:
                    summary += (
                        f"  {phase_name}:\n"
                        f"    Duration: {phase['duration']:.2f}s\n"
                        f"    API Calls: {phase['api_calls']}\n"
                        f"    Tokens: {phase['input_tokens']:,} in / {phase['output_tokens']:,} out\n"
                        f"    Cost: ${phase.get('cost', 0):.4f}\n"
                    )

            if self.errors:
                summary += f"\nERRORS ENCOUNTERED: {len(self.errors)}\n"
                for err in self.errors:
                    summary += f"  [{err['time']}] {err['phase']}: {err['error']}\n"

            summary += f"\nLog file: {self.log_file}\n"
            summary += f"Cost report: {self.cost_file}\n"

            self._append_log(summary)

            # Write detailed cost report
            cost_report = {
                "task_name": self.task_name,
                "model": self.model_name,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(end_time).isoformat(),
                "duration_seconds": round(total_duration, 2),
                "parameters": self.parameters,
                "totals": {
                    "api_calls": self.api_calls,
                    "input_tokens": self.total_input_tokens,
                    "output_tokens": self.total_output_tokens,
                    "total_tokens": self.total_input_tokens + self.total_output_tokens,
                    "cost_usd": round(total_cost, 4)
                },
                "phases": self.phases,
                "errors": self.errors,
                "pricing": get_pricing().get(self.model_name, {})
            }

            with open(self.cost_file, 'w') as f:
                json.dump(cost_report, f, indent=2)

            print(f"\n{'='*80}")
            print(f"Cost Tracking Summary")
            print(f"{'='*80}")
            print(f"Total Cost: ${total_cost:.4f}")
            print(f"Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}")
            print(f"API Calls: {self.api_calls}")
            print(f"Duration: {total_duration:.2f}s")
            print(f"\nDetailed logs saved to: {self.log_file}")
            print(f"Cost report saved to: {self.cost_file}")
            print(f"{'='*80}\n")

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token counts."""
        pricing = get_pricing().get(self.model_name, {"input": 0, "output": 0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%H:%M:%S")

    def _append_log(self, message: str):
        """Append message to log file."""
        with open(self.log_file, 'a') as f:
            f.write(message)


class MockCostTracker:
    """Mock tracker for dry-run mode."""

    def __init__(self, *args, **kwargs):
        pass

    def set_parameters(self, params):
        pass

    def start_phase(self, phase_name):
        pass

    def end_phase(self, phase_name, status="completed"):
        pass

    def record_api_call(self, *args, **kwargs):
        pass

    def record_event(self, *args, **kwargs):
        pass

    def finalize(self):
        print("\n[DRY RUN MODE] No costs to track")


def estimate_tokens(text: str) -> int:
    """Rough estimate of tokens (1 token ≈ 4 characters)."""
    return len(text) // 4
