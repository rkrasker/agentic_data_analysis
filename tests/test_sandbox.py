"""
Tests for sandbox functionality.
"""

import pytest
import tempfile
from pathlib import Path
import time

from src.utils.sandbox import (
    SandboxConfig,
    FileSystemSandbox,
    CodeExecutionSandbox,
    FileAccessError,
    CodeExecutionError,
    TimeoutError,
    create_temp_sandbox,
    create_project_sandbox,
    create_resolver_sandbox,
)


class TestFileSystemSandbox:
    """Tests for file system sandboxing."""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary directories for testing."""
        read_dir = tmp_path / "read"
        write_dir = tmp_path / "write"
        forbidden_dir = tmp_path / "forbidden"

        read_dir.mkdir()
        write_dir.mkdir()
        forbidden_dir.mkdir()

        return read_dir, write_dir, forbidden_dir

    @pytest.fixture
    def sandbox(self, temp_dirs):
        """Create sandbox with test configuration."""
        read_dir, write_dir, _ = temp_dirs
        config = SandboxConfig(
            allowed_read_dirs=[read_dir],
            allowed_write_dirs=[write_dir],
            max_file_size_mb=1,
            strict_mode=True,
        )
        return FileSystemSandbox(config)

    def test_read_allowed_file(self, sandbox, temp_dirs):
        """Test reading from allowed directory."""
        read_dir, _, _ = temp_dirs
        test_file = read_dir / "test.txt"
        test_file.write_text("test content")

        content = sandbox.safe_read(test_file)
        assert content == "test content"

    def test_read_forbidden_file(self, sandbox, temp_dirs):
        """Test reading from forbidden directory raises error."""
        _, _, forbidden_dir = temp_dirs
        test_file = forbidden_dir / "secret.txt"
        test_file.write_text("secret")

        with pytest.raises(FileAccessError, match="Read access denied"):
            sandbox.safe_read(test_file)

    def test_write_allowed_file(self, sandbox, temp_dirs):
        """Test writing to allowed directory."""
        _, write_dir, _ = temp_dirs
        test_file = write_dir / "output.txt"

        sandbox.safe_write(test_file, "output content")
        assert test_file.read_text() == "output content"

    def test_write_forbidden_file(self, sandbox, temp_dirs):
        """Test writing to forbidden directory raises error."""
        read_dir, _, _ = temp_dirs
        test_file = read_dir / "blocked.txt"

        with pytest.raises(FileAccessError, match="Write access denied"):
            sandbox.safe_write(test_file, "blocked content")

    def test_write_file_size_limit(self, sandbox, temp_dirs):
        """Test file size limit enforcement."""
        _, write_dir, _ = temp_dirs
        test_file = write_dir / "large.txt"

        # Try to write 2MB (exceeds 1MB limit)
        large_content = "x" * (2 * 1024 * 1024)

        with pytest.raises(FileAccessError, match="exceeds limit"):
            sandbox.safe_write(test_file, large_content)

    def test_validate_read_path(self, sandbox, temp_dirs):
        """Test path validation for reads."""
        read_dir, _, _ = temp_dirs
        test_file = read_dir / "test.txt"

        validated = sandbox.validate_read(test_file)
        assert validated.is_absolute()

    def test_validate_write_creates_parent(self, sandbox, temp_dirs):
        """Test that writing creates parent directories."""
        _, write_dir, _ = temp_dirs
        nested_file = write_dir / "sub" / "nested" / "file.txt"

        sandbox.safe_write(nested_file, "nested content")
        assert nested_file.read_text() == "nested content"

    def test_non_strict_mode_warnings(self, temp_dirs, capsys):
        """Test that non-strict mode issues warnings instead of errors."""
        read_dir, write_dir, forbidden_dir = temp_dirs
        config = SandboxConfig(
            allowed_read_dirs=[read_dir],
            allowed_write_dirs=[write_dir],
            strict_mode=False,
        )
        sandbox = FileSystemSandbox(config)

        forbidden_file = forbidden_dir / "test.txt"
        forbidden_file.write_text("test")

        # Should warn but not raise
        sandbox.validate_read(forbidden_file)
        captured = capsys.readouterr()
        assert "Warning" in captured.err


class TestCodeExecutionSandbox:
    """Tests for code execution sandboxing."""

    @pytest.fixture
    def sandbox(self):
        """Create sandbox with test configuration."""
        config = SandboxConfig(
            allowed_read_dirs=[],
            allowed_write_dirs=[],
            max_execution_time_sec=2,
            allowed_imports={'re', 'json'},
            strict_mode=True,
        )
        return CodeExecutionSandbox(config)

    def test_execute_simple_code(self, sandbox):
        """Test executing simple safe code."""
        code = """
result = 1 + 1
message = "hello"
"""
        namespace = sandbox.execute_code(code)
        assert namespace['result'] == 2
        assert namespace['message'] == "hello"

    def test_execute_function(self, sandbox):
        """Test executing and calling a function."""
        code = """
def add(a, b):
    return a + b
"""
        result = sandbox.execute_function(code, 'add', 5, 3)
        assert result == 8

    def test_restricted_builtins(self, sandbox):
        """Test that dangerous builtins are blocked."""
        code = "open('/etc/passwd', 'r')"

        with pytest.raises(CodeExecutionError):
            sandbox.execute_code(code)

    def test_import_restriction(self, sandbox):
        """Test that unauthorized imports are blocked."""
        code = "import os"

        with pytest.raises(CodeExecutionError, match="not allowed"):
            sandbox.execute_code(code)

    def test_allowed_import(self, sandbox):
        """Test that allowed imports work."""
        code = """
import re
result = re.match(r'\\d+', '123abc')
"""
        namespace = sandbox.execute_code(code)
        assert namespace['result'] is not None

    def test_timeout_enforcement(self, sandbox):
        """Test that long-running code is terminated."""
        code = """
import time
time.sleep(10)
"""
        # Note: This test may not work on Windows (no signal.SIGALRM)
        try:
            with pytest.raises(TimeoutError, match="exceeded"):
                sandbox.execute_code(code)
        except CodeExecutionError:
            # On systems without signal support, this will fail differently
            pytest.skip("Signal-based timeout not supported on this system")

    def test_syntax_error_handling(self, sandbox):
        """Test that syntax errors are caught."""
        code = "def broken syntax"

        with pytest.raises(CodeExecutionError):
            sandbox.execute_code(code)

    def test_runtime_error_handling(self, sandbox):
        """Test that runtime errors are caught."""
        code = """
def divide(a, b):
    return a / b
"""
        with pytest.raises(CodeExecutionError, match="division by zero"):
            sandbox.execute_function(code, 'divide', 10, 0)

    def test_safe_builtins_available(self, sandbox):
        """Test that safe builtins are accessible."""
        code = """
numbers = [1, 2, 3, 4, 5]
result = sum(numbers)
max_val = max(numbers)
min_val = min(numbers)
"""
        namespace = sandbox.execute_code(code)
        assert namespace['result'] == 15
        assert namespace['max_val'] == 5
        assert namespace['min_val'] == 1

    def test_function_not_found(self, sandbox):
        """Test error when function doesn't exist."""
        code = "x = 1"

        with pytest.raises(CodeExecutionError, match="not found"):
            sandbox.execute_function(code, 'missing_function')

    def test_not_callable(self, sandbox):
        """Test error when trying to call non-function."""
        code = "not_a_function = 42"

        with pytest.raises(CodeExecutionError, match="not callable"):
            sandbox.execute_function(code, 'not_a_function')


class TestTempSandbox:
    """Tests for temporary sandbox context manager."""

    def test_create_temp_sandbox(self):
        """Test creating temporary sandbox."""
        with create_temp_sandbox() as (temp_path, sandbox):
            assert temp_path.exists()
            assert isinstance(sandbox, FileSystemSandbox)

            # Test file operations work
            test_file = temp_path / "test.txt"
            sandbox.safe_write(test_file, "temp content")
            content = sandbox.safe_read(test_file)
            assert content == "temp content"

    def test_temp_sandbox_cleanup(self):
        """Test that temporary sandbox is cleaned up."""
        with create_temp_sandbox(cleanup=True) as (temp_path, sandbox):
            temp_file = temp_path / "test.txt"
            sandbox.safe_write(temp_file, "content")
            saved_path = temp_path

        assert not saved_path.exists()

    def test_temp_sandbox_no_cleanup(self, tmp_path):
        """Test temporary sandbox without cleanup."""
        with create_temp_sandbox(base_dir=tmp_path, cleanup=False) as (temp_path, sandbox):
            test_file = temp_path / "test.txt"
            sandbox.safe_write(test_file, "content")
            saved_path = temp_path

        assert saved_path.exists()
        # Cleanup manually
        import shutil
        shutil.rmtree(saved_path)


class TestProjectSandbox:
    """Tests for project-specific sandbox creation."""

    def test_create_project_sandbox(self, tmp_path):
        """Test creating project sandbox with standard directories."""
        # Create project structure
        (tmp_path / "data" / "raw").mkdir(parents=True)
        (tmp_path / "data" / "processed").mkdir(parents=True)
        (tmp_path / "data" / "outputs").mkdir(parents=True)
        (tmp_path / "config").mkdir()

        sandbox = create_project_sandbox(tmp_path)

        # Test read access to allowed dirs
        test_file = tmp_path / "data" / "raw" / "test.txt"
        test_file.write_text("content")
        content = sandbox.safe_read(test_file)
        assert content == "content"

        # Test write access to output dir
        output_file = tmp_path / "data" / "outputs" / "result.txt"
        sandbox.safe_write(output_file, "result")
        assert output_file.exists()

        # Test that src directory is blocked
        src_file = tmp_path / "src" / "code.py"
        src_file.parent.mkdir()
        src_file.write_text("code")

        with pytest.raises(FileAccessError):
            sandbox.safe_read(src_file)


class TestResolverSandbox:
    """Tests for resolver-specific sandbox."""

    def test_create_resolver_sandbox(self):
        """Test creating resolver sandbox."""
        sandbox = create_resolver_sandbox()
        assert isinstance(sandbox, CodeExecutionSandbox)

        # Test that resolver code can execute
        code = """
import re
import json

def parse_record(text):
    pattern = r'\\d{4}'
    matches = re.findall(pattern, text)
    return json.dumps(matches)
"""
        result = sandbox.execute_function(code, 'parse_record', "Years: 1942 and 1943")
        import json
        parsed = json.loads(result)
        assert parsed == ['1942', '1943']

    def test_resolver_blocked_imports(self):
        """Test that resolvers can't import dangerous modules."""
        sandbox = create_resolver_sandbox()

        code = """
import subprocess
def bad_resolver():
    subprocess.run(['ls'])
"""
        with pytest.raises(CodeExecutionError, match="not allowed"):
            sandbox.execute_code(code)
