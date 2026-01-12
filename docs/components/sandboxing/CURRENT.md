# Sandboxing

**Last Updated:** 2026-01-12
**Version:** 1.0

## Overview

Sandboxing provides security controls for file system access and code execution, protecting against:
- Unauthorized file access
- Malicious or buggy LLM-generated code
- Resource exhaustion attacks
- Data exfiltration

## Architecture

Two-layer sandboxing approach:

```
┌─────────────────────────────────────┐
│     File System Sandbox             │
│  - Path validation                  │
│  - Read/write restrictions          │
│  - File size limits                 │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│     Code Execution Sandbox          │
│  - Restricted builtins              │
│  - Import filtering                 │
│  - Timeout enforcement              │
│  - Isolated namespace               │
└─────────────────────────────────────┘
```

## Components

### FileSystemSandbox

Controls all file operations through allowlists:

**Read Access:**
- `data/raw/` - Input data
- `data/processed/` - Preprocessed data
- `config/` - Configuration files
- `hierarchies/`, `resolvers/`, `prompts/` - Runtime assets

**Write Access:**
- `data/processed/` - Intermediate results
- `data/outputs/` - Final outputs
- `data/validation/` - Validation results

**Features:**
- Path validation against allowlists
- Automatic parent directory creation
- File size limits (default 500MB)
- Strict mode (errors) vs permissive (warnings)

### CodeExecutionSandbox

Executes untrusted code safely:

**Restrictions:**
- Limited builtins (no `open`, `__import__`, `eval`, etc.)
- Import whitelist (default: `re`, `json`, `typing`, `dataclasses`, `datetime`)
- Execution timeout (default 30s)
- Isolated namespace (no access to parent scope)

**Allowed Operations:**
- Safe builtins: `len`, `sum`, `max`, `min`, `sorted`, etc.
- String/numeric operations
- Data structure manipulation
- Approved module imports

## Usage

### Basic File Operations

```python
from src.utils.sandbox import create_project_sandbox
from pathlib import Path

# Create sandbox with project defaults
project_root = Path(__file__).parent.parent
sandbox = create_project_sandbox(project_root)

# Safe read
content = sandbox.safe_read('data/raw/records.csv')

# Safe write
sandbox.safe_write('data/outputs/results.json', json_data)

# Validate paths without reading
try:
    path = sandbox.validate_write('data/outputs/new_file.txt')
except FileAccessError:
    print("Access denied")
```

### Code Execution

```python
from src.utils.sandbox import create_resolver_sandbox

sandbox = create_resolver_sandbox()

# Execute code and get namespace
code = """
import re

def extract_year(text):
    match = re.search(r'\\b(19|20)\\d{2}\\b', text)
    return match.group(0) if match else None
"""

namespace = sandbox.execute_code(code)
extract_year = namespace['extract_year']
result = extract_year("Served in 1942")  # Returns "1942"

# Or execute function directly
result = sandbox.execute_function(
    code,
    'extract_year',
    "Served in 1942"
)
```

### Temporary Sandbox

```python
from src.utils.sandbox import create_temp_sandbox

# Creates isolated temp directory
with create_temp_sandbox() as (temp_path, sandbox):
    # Work with temporary files
    test_file = temp_path / "temp.txt"
    sandbox.safe_write(test_file, "temporary data")

    # Process...

# Automatically cleaned up on exit
```

### Custom Configuration

```python
from src.utils.sandbox import SandboxConfig, FileSystemSandbox
from pathlib import Path

config = SandboxConfig(
    allowed_read_dirs=[Path('data/raw')],
    allowed_write_dirs=[Path('data/outputs')],
    max_file_size_mb=100,
    max_execution_time_sec=60,
    allowed_imports={'re', 'json', 'csv'},
    strict_mode=True,
)

fs_sandbox = FileSystemSandbox(config)
code_sandbox = CodeExecutionSandbox(config)
```

## Configuration

Configuration in `config/sandbox.yaml`:

```yaml
file_system:
  allowed_read_dirs: [...]
  allowed_write_dirs: [...]
  max_file_size_mb: 500
  strict_mode: true

code_execution:
  max_execution_time_sec: 30
  allowed_imports: [re, json, typing, ...]
  strict_mode: true

resolver:
  enabled: true
  log_executions: true
```

Strategy-specific overrides supported.

## Security Considerations

### What's Protected

✓ File system access outside allowed directories
✓ Import of dangerous modules (`os`, `sys`, `subprocess`, etc.)
✓ Access to dangerous builtins (`eval`, `exec`, `__import__`, `open`)
✓ Long-running code execution
✓ Excessive file sizes

### What's NOT Protected

✗ CPU exhaustion within timeout (e.g., `while True` for 29s)
✗ Memory exhaustion (requires OS-level controls)
✗ Sophisticated obfuscation attacks
✗ Side-channel attacks

**Recommendation:** Only execute code from trusted sources or reviewed by humans.

## Resolver Integration

Resolvers are automatically sandboxed when executed:

```python
# In strategy execution
from src.utils.sandbox import create_resolver_sandbox

sandbox = create_resolver_sandbox()

# Load resolver code from file
resolver_code = load_resolver('config/resolvers/year_parser.py')

# Execute safely
result = sandbox.execute_function(
    resolver_code,
    'resolve',
    record_text,
    hierarchy
)
```

Resolver logging captures:
- Execution time
- Input/output
- Exceptions
- Timeout violations

## Testing

Comprehensive test suite in `tests/test_sandbox.py`:

- File access enforcement
- Code execution restrictions
- Timeout behavior
- Import filtering
- Error handling
- Integration scenarios

Run tests:
```bash
pytest tests/test_sandbox.py -v
```

## Performance Impact

**File Operations:**
- Negligible overhead (~1-5ms per operation)
- Path validation is fast (set lookups)

**Code Execution:**
- Compilation overhead: ~5-20ms
- Execution overhead: minimal (native Python)
- Timeout via signals (Unix): no overhead
- Timeout via threading (Windows): slight overhead

## Limitations

### Platform-Specific

- **Unix/Linux/macOS:** Full timeout support via `signal.SIGALRM`
- **Windows:** Limited timeout support (may require threading approach)

### Python Version

- Requires Python 3.9+ for `Path.is_relative_to()`
- Older versions need alternative path checking

### Not a VM

This is **not** a full virtual machine or container. For maximum isolation, consider:
- Docker containers
- `subprocess` with limited permissions
- Virtual machines
- Cloud function isolation

## Future Enhancements

Potential improvements:

- [ ] Memory limits via `resource` module (Unix)
- [ ] Network access blocking
- [ ] Filesystem quota enforcement
- [ ] Docker/container integration
- [ ] Audit logging to file
- [ ] Rate limiting for repeated executions
- [ ] AST-based import validation (more robust)
- [ ] Bytecode analysis for hidden imports

## References

- Python `compile()` and `exec()` documentation
- [PEP 578](https://peps.python.org/pep-0578/) - Python Runtime Audit Hooks
- OWASP Code Injection Prevention
- Principle of Least Privilege
