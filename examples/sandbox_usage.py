"""
Example usage of sandboxing features.

Demonstrates both file system and code execution sandboxing.
"""

from pathlib import Path
from src.utils.sandbox import (
    create_project_sandbox,
    create_resolver_sandbox,
    create_temp_sandbox,
    FileAccessError,
    CodeExecutionError,
)


def example_file_operations():
    """Example of sandboxed file operations."""
    print("=== File System Sandboxing Example ===\n")

    project_root = Path(__file__).parent.parent
    sandbox = create_project_sandbox(project_root)

    # Safe read from allowed directory
    try:
        print("✓ Reading from allowed directory (data/raw)...")
        # Would work if file exists
        # content = sandbox.safe_read('data/raw/sample.csv')
        print("  Access granted\n")
    except FileAccessError as e:
        print(f"  ✗ {e}\n")

    # Safe write to allowed directory
    try:
        print("✓ Writing to allowed directory (data/outputs)...")
        sandbox.safe_write(
            project_root / 'data/outputs/example.txt',
            "Example output"
        )
        print("  Write successful\n")
    except FileAccessError as e:
        print(f"  ✗ {e}\n")

    # Blocked write to restricted directory
    try:
        print("✗ Attempting to write to restricted directory (src)...")
        sandbox.safe_write(
            project_root / 'src/malicious.py',
            "import os; os.system('rm -rf /')"
        )
        print("  !! Write should have been blocked\n")
    except FileAccessError as e:
        print(f"  ✓ Blocked: {e}\n")


def example_code_execution():
    """Example of sandboxed code execution."""
    print("=== Code Execution Sandboxing Example ===\n")

    sandbox = create_resolver_sandbox()

    # Safe code execution
    safe_code = """
import re
import json

def parse_military_record(text):
    # Extract years
    years = re.findall(r'\\b(19|20)\\d{2}\\b', text)

    # Extract unit patterns
    units = re.findall(r'\\b\\d+(?:st|nd|rd|th)\\s+\\w+', text)

    return {
        'years': years,
        'units': units
    }
"""

    try:
        print("✓ Executing safe resolver code...")
        result = sandbox.execute_function(
            safe_code,
            'parse_military_record',
            "Served in 42nd Infantry from 1942 to 1945"
        )
        print(f"  Result: {result}\n")
    except CodeExecutionError as e:
        print(f"  ✗ {e}\n")

    # Blocked dangerous code - file access
    dangerous_code_1 = """
def malicious_resolver(text):
    with open('/etc/passwd', 'r') as f:
        return f.read()
"""

    try:
        print("✗ Attempting to execute code with file access...")
        sandbox.execute_function(
            dangerous_code_1,
            'malicious_resolver',
            "test"
        )
        print("  !! Execution should have been blocked\n")
    except CodeExecutionError as e:
        print(f"  ✓ Blocked: {e}\n")

    # Blocked dangerous code - unauthorized import
    dangerous_code_2 = """
import subprocess

def malicious_resolver(text):
    subprocess.run(['ls', '-la'])
    return text
"""

    try:
        print("✗ Attempting to import unauthorized module (subprocess)...")
        sandbox.execute_code(dangerous_code_2)
        print("  !! Import should have been blocked\n")
    except CodeExecutionError as e:
        print(f"  ✓ Blocked: {e}\n")

    # Allowed imports work fine
    allowed_code = """
import json
from dataclasses import dataclass
from typing import List

@dataclass
class Record:
    year: int
    unit: str

def structured_parser(text: str) -> str:
    record = Record(year=1942, unit="42nd Infantry")
    return json.dumps({'year': record.year, 'unit': record.unit})
"""

    try:
        print("✓ Executing code with allowed imports (json, dataclasses, typing)...")
        result = sandbox.execute_function(
            allowed_code,
            'structured_parser',
            "test"
        )
        print(f"  Result: {result}\n")
    except CodeExecutionError as e:
        print(f"  ✗ {e}\n")


def example_temp_sandbox():
    """Example of temporary sandbox."""
    print("=== Temporary Sandbox Example ===\n")

    with create_temp_sandbox() as (temp_path, sandbox):
        print(f"✓ Created temporary sandbox at: {temp_path}")

        # Create and work with temporary files
        temp_file = temp_path / "processing.txt"
        sandbox.safe_write(temp_file, "Temporary processing data")

        content = sandbox.safe_read(temp_file)
        print(f"  Read from temp file: {content[:30]}...")

        # Can create subdirectories
        sub_dir = temp_path / "results"
        sub_dir.mkdir()
        result_file = sub_dir / "output.json"
        sandbox.safe_write(result_file, '{"status": "complete"}')

        print("  ✓ Temporary operations successful")

    print("  ✓ Temporary sandbox cleaned up\n")


def example_error_handling():
    """Example of proper error handling."""
    print("=== Error Handling Example ===\n")

    sandbox = create_resolver_sandbox()

    # Handle syntax errors
    bad_syntax = "def broken function"
    try:
        sandbox.execute_code(bad_syntax)
    except CodeExecutionError as e:
        print(f"✓ Caught syntax error: {e}\n")

    # Handle runtime errors
    runtime_error_code = """
def divide(a, b):
    return a / b
"""
    try:
        sandbox.execute_function(runtime_error_code, 'divide', 10, 0)
    except CodeExecutionError as e:
        print(f"✓ Caught runtime error: {e}\n")

    # Handle missing functions
    try:
        sandbox.execute_function("x = 1", 'nonexistent_function')
    except CodeExecutionError as e:
        print(f"✓ Caught missing function error: {e}\n")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SANDBOXING EXAMPLES")
    print("="*60 + "\n")

    example_file_operations()
    print("-" * 60 + "\n")

    example_code_execution()
    print("-" * 60 + "\n")

    example_temp_sandbox()
    print("-" * 60 + "\n")

    example_error_handling()

    print("="*60)
    print("All examples completed!")
    print("="*60 + "\n")
