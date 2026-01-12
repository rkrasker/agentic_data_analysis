"""
Sandboxing utilities for safe file access and code execution.

Provides controlled environments for:
- File system access (read/write restrictions)
- Code execution (isolated namespace, resource limits)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from contextlib import contextmanager
import tempfile
import shutil
import io
from dataclasses import dataclass
import signal


@dataclass
class SandboxConfig:
    """Configuration for sandbox behavior."""

    # File system permissions
    allowed_read_dirs: List[Path]
    allowed_write_dirs: List[Path]
    max_file_size_mb: int = 100

    # Code execution limits
    max_execution_time_sec: int = 30
    max_memory_mb: Optional[int] = None
    allowed_imports: Optional[Set[str]] = None

    # Strict mode - raise errors vs warnings
    strict_mode: bool = True


class SandboxError(Exception):
    """Base exception for sandbox violations."""
    pass


class FileAccessError(SandboxError):
    """Raised when file access is denied."""
    pass


class CodeExecutionError(SandboxError):
    """Raised when code execution violates sandbox rules."""
    pass


class TimeoutError(SandboxError):
    """Raised when execution exceeds time limit."""
    pass


class FileSystemSandbox:
    """
    Sandbox for controlled file system access.

    Validates all file operations against allowed directories.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._allowed_read_paths = {p.resolve() for p in config.allowed_read_dirs}
        self._allowed_write_paths = {p.resolve() for p in config.allowed_write_dirs}

    def _is_path_allowed(self, path: Path, allowed_dirs: Set[Path]) -> bool:
        """Check if path is within allowed directories."""
        resolved = path.resolve()
        return any(
            resolved == allowed or resolved.is_relative_to(allowed)
            for allowed in allowed_dirs
        )

    def validate_read(self, path: Union[str, Path]) -> Path:
        """
        Validate that path can be read.

        Args:
            path: Path to validate

        Returns:
            Resolved path if allowed

        Raises:
            FileAccessError: If access denied
        """
        path = Path(path)

        if not self._is_path_allowed(path, self._allowed_read_paths):
            msg = f"Read access denied: {path}"
            if self.config.strict_mode:
                raise FileAccessError(msg)
            print(f"Warning: {msg}", file=sys.stderr)

        return path.resolve()

    def validate_write(self, path: Union[str, Path]) -> Path:
        """
        Validate that path can be written.

        Args:
            path: Path to validate

        Returns:
            Resolved path if allowed

        Raises:
            FileAccessError: If access denied
        """
        path = Path(path)

        if not self._is_path_allowed(path, self._allowed_write_paths):
            msg = f"Write access denied: {path}"
            if self.config.strict_mode:
                raise FileAccessError(msg)
            print(f"Warning: {msg}", file=sys.stderr)

        return path.resolve()

    def safe_read(self, path: Union[str, Path], mode: str = 'r') -> Any:
        """
        Safely read a file with validation.

        Args:
            path: Path to read
            mode: File open mode

        Returns:
            File contents
        """
        validated_path = self.validate_read(path)
        with open(validated_path, mode) as f:
            return f.read()

    def safe_write(self, path: Union[str, Path], content: Any, mode: str = 'w') -> None:
        """
        Safely write a file with validation.

        Args:
            path: Path to write
            content: Content to write
            mode: File open mode
        """
        validated_path = self.validate_write(path)

        # Check file size limit if writing text
        if isinstance(content, str):
            size_mb = len(content.encode('utf-8')) / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                raise FileAccessError(
                    f"File size {size_mb:.2f}MB exceeds limit of {self.config.max_file_size_mb}MB"
                )

        # Ensure parent directory exists
        validated_path.parent.mkdir(parents=True, exist_ok=True)

        with open(validated_path, mode) as f:
            f.write(content)


class CodeExecutionSandbox:
    """
    Sandbox for safe execution of untrusted code.

    Provides isolated namespace and resource limits.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config

    def _timeout_handler(self, signum, frame):
        """Signal handler for execution timeout."""
        raise TimeoutError(f"Execution exceeded {self.config.max_execution_time_sec}s limit")

    def _build_restricted_globals(self) -> Dict[str, Any]:
        """Build restricted global namespace for code execution."""

        # Safe builtins
        safe_builtins = {
            'abs': abs,
            'all': all,
            'any': any,
            'bool': bool,
            'dict': dict,
            'enumerate': enumerate,
            'float': float,
            'int': int,
            'len': len,
            'list': list,
            'max': max,
            'min': min,
            'range': range,
            'round': round,
            'set': set,
            'sorted': sorted,
            'str': str,
            'sum': sum,
            'tuple': tuple,
            'zip': zip,
            # Add safe exceptions
            'Exception': Exception,
            'ValueError': ValueError,
            'KeyError': KeyError,
            'TypeError': TypeError,
        }

        restricted_globals = {
            '__builtins__': safe_builtins,
            '__name__': '__sandbox__',
            '__doc__': None,
        }

        return restricted_globals

    def execute_code(
        self,
        code: str,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute code in sandboxed environment.

        Args:
            code: Python code to execute
            globals_dict: Additional globals to provide
            locals_dict: Local variables namespace

        Returns:
            Local namespace after execution

        Raises:
            CodeExecutionError: If code execution fails or violates rules
            TimeoutError: If execution exceeds time limit
        """

        # Build restricted namespace
        restricted_globals = self._build_restricted_globals()
        if globals_dict:
            restricted_globals.update(globals_dict)

        restricted_locals = locals_dict or {}

        # Validate imports if restricted
        if self.config.allowed_imports is not None:
            if 'import ' in code or 'from ' in code:
                # Simple check - could be more sophisticated
                for line in code.split('\n'):
                    line = line.strip()
                    if line.startswith('import ') or line.startswith('from '):
                        module = line.split()[1].split('.')[0]
                        if module not in self.config.allowed_imports:
                            raise CodeExecutionError(
                                f"Import of '{module}' not allowed. "
                                f"Allowed imports: {self.config.allowed_imports}"
                            )

        # Set up timeout using signal (Unix only)
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.config.max_execution_time_sec)

        try:
            # Compile first to check for syntax errors
            compiled_code = compile(code, '<sandbox>', 'exec')

            # Execute in restricted environment
            exec(compiled_code, restricted_globals, restricted_locals)

            return restricted_locals

        except TimeoutError:
            raise
        except Exception as e:
            raise CodeExecutionError(f"Code execution failed: {e}") from e
        finally:
            # Restore signal handler
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

    def execute_function(
        self,
        code: str,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function defined in code and call it with arguments.

        Args:
            code: Python code containing function definition
            function_name: Name of function to call
            *args: Positional arguments to function
            **kwargs: Keyword arguments to function

        Returns:
            Function return value
        """
        namespace = self.execute_code(code)

        if function_name not in namespace:
            raise CodeExecutionError(f"Function '{function_name}' not found in code")

        func = namespace[function_name]
        if not callable(func):
            raise CodeExecutionError(f"'{function_name}' is not callable")

        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise CodeExecutionError(f"Function execution failed: {e}") from e


@contextmanager
def create_temp_sandbox(
    base_dir: Optional[Path] = None,
    cleanup: bool = True
):
    """
    Create temporary sandbox with isolated directory structure.

    Args:
        base_dir: Base directory for temp sandbox (default: system temp)
        cleanup: Whether to cleanup on exit

    Yields:
        Tuple of (temp_path, FileSystemSandbox)
    """
    temp_path = Path(tempfile.mkdtemp(dir=base_dir))

    try:
        config = SandboxConfig(
            allowed_read_dirs=[temp_path],
            allowed_write_dirs=[temp_path],
        )
        sandbox = FileSystemSandbox(config)

        yield temp_path, sandbox

    finally:
        if cleanup and temp_path.exists():
            shutil.rmtree(temp_path)


def create_project_sandbox(project_root: Path) -> FileSystemSandbox:
    """
    Create sandbox for project with standard directory access.

    Args:
        project_root: Root directory of project

    Returns:
        Configured FileSystemSandbox
    """
    config = SandboxConfig(
        allowed_read_dirs=[
            project_root / 'data' / 'raw',
            project_root / 'data' / 'processed',
            project_root / 'config',
            project_root / 'hierarchies',
            project_root / 'resolvers',
            project_root / 'prompts',
        ],
        allowed_write_dirs=[
            project_root / 'data' / 'processed',
            project_root / 'data' / 'outputs',
            project_root / 'data' / 'validation',
        ],
        max_file_size_mb=500,
        strict_mode=True,
    )

    return FileSystemSandbox(config)


def create_resolver_sandbox() -> CodeExecutionSandbox:
    """
    Create sandbox for resolver code execution.

    Returns:
        Configured CodeExecutionSandbox
    """
    config = SandboxConfig(
        allowed_read_dirs=[],  # File access handled separately
        allowed_write_dirs=[],
        max_execution_time_sec=30,
        allowed_imports={'re', 'json', 'typing', 'dataclasses', 'datetime'},
        strict_mode=True,
    )

    return CodeExecutionSandbox(config)
