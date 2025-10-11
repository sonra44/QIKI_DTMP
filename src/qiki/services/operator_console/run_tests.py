#!/usr/bin/env python3
"""
Test runner script for QIKI Operator Console.
Provides various test execution options with reporting.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle output."""
    print(f"\n{'='*60}")
    print(f"Running: {description if description else ' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True, cwd=Path(__file__).parent)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def run_tests(args):
    """Run tests with specified configuration."""
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test path
    if args.path:
        cmd.append(args.path)
    else:
        cmd.append("tests/")
    
    # Add verbosity
    if args.verbose:
        cmd.extend(["-v", "-s"])
    elif args.quiet:
        cmd.append("-q")
    
    # Add markers
    if args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])
    elif args.grpc:
        cmd.extend(["-m", "grpc"])
    elif args.ui:
        cmd.extend(["-m", "ui"])
    elif args.i18n:
        cmd.extend(["-m", "i18n"])
    elif args.metrics:
        cmd.extend(["-m", "metrics"])
    
    # Add coverage options
    if args.coverage:
        cmd.extend([
            "--cov=.",
            "--cov-report=html:coverage_html",
            "--cov-report=term-missing",
            "--cov-report=xml:coverage.xml"
        ])
        if args.cov_fail:
            cmd.extend([f"--cov-fail-under={args.cov_fail}"])
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])
    
    # Add specific test patterns
    if args.pattern:
        cmd.extend(["-k", args.pattern])
    
    # Add custom options
    if args.options:
        cmd.extend(args.options.split())
    
    # Run the tests
    success = run_command(cmd, "Running tests")
    
    if args.coverage and success:
        print(f"\nCoverage report saved to: {Path('coverage_html/index.html').absolute()}")
    
    return success


def run_linting(args):
    """Run code linting and formatting checks."""
    success = True
    
    if args.ruff or args.all_lint:
        # Run ruff for linting
        success &= run_command([
            "python", "-m", "ruff", "check", ".",
            "--config", "pyproject.toml" if Path("pyproject.toml").exists() else "setup.cfg"
        ], "Ruff linting")
        
        # Run ruff for formatting
        if args.fix:
            success &= run_command([
                "python", "-m", "ruff", "format", ".",
                "--config", "pyproject.toml" if Path("pyproject.toml").exists() else "setup.cfg"
            ], "Ruff formatting")
    
    if args.pylint or args.all_lint:
        # Run pylint
        success &= run_command([
            "python", "-m", "pylint", ".",
            "--rcfile=.pylintrc" if Path(".pylintrc").exists() else "--disable=all"
        ], "Pylint analysis")
    
    if args.mypy or args.all_lint:
        # Run mypy
        success &= run_command([
            "python", "-m", "mypy", ".",
            "--config-file=mypy.ini" if Path("mypy.ini").exists() else "--ignore-missing-imports"
        ], "MyPy type checking")
    
    return success


def run_security_checks():
    """Run security vulnerability checks."""
    success = True
    
    # Check for known vulnerabilities in dependencies
    try:
        success &= run_command([
            "python", "-m", "pip", "audit"
        ], "Security audit")
    except FileNotFoundError:
        print("pip audit not available, skipping security check")
    
    return success


def generate_report():
    """Generate test and coverage reports."""
    print("\n" + "="*60)
    print("GENERATING REPORTS")
    print("="*60)
    
    # Coverage report
    if Path("coverage.xml").exists():
        print(f"Coverage XML: {Path('coverage.xml').absolute()}")
    
    if Path("coverage_html").exists():
        print(f"Coverage HTML: {Path('coverage_html/index.html').absolute()}")
    
    # Test results
    if Path("pytest.xml").exists():
        print(f"Test results XML: {Path('pytest.xml').absolute()}")


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for QIKI Operator Console",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                     # Run all tests
  python run_tests.py --unit --coverage  # Run unit tests with coverage
  python run_tests.py --integration -v   # Run integration tests verbose
  python run_tests.py --lint --fix       # Run linting with auto-fix
  python run_tests.py --grpc -k "test_connect"  # Run gRPC tests matching pattern
        """
    )
    
    # Test selection
    test_group = parser.add_argument_group("Test Selection")
    test_group.add_argument("--unit", action="store_true", help="Run only unit tests")
    test_group.add_argument("--integration", action="store_true", help="Run only integration tests")
    test_group.add_argument("--grpc", action="store_true", help="Run only gRPC tests")
    test_group.add_argument("--ui", action="store_true", help="Run only UI/widget tests")
    test_group.add_argument("--i18n", action="store_true", help="Run only i18n tests")
    test_group.add_argument("--metrics", action="store_true", help="Run only metrics tests")
    test_group.add_argument("--path", help="Specific test path or file")
    test_group.add_argument("--pattern", help="Test name pattern to match")
    
    # Test execution
    exec_group = parser.add_argument_group("Test Execution")
    exec_group.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    exec_group.add_argument("-q", "--quiet", action="store_true", help="Quiet output")
    exec_group.add_argument("--parallel", type=int, help="Run tests in parallel (number of processes)")
    exec_group.add_argument("--options", help="Additional pytest options")
    
    # Coverage
    cov_group = parser.add_argument_group("Coverage")
    cov_group.add_argument("--coverage", action="store_true", help="Generate coverage report")
    cov_group.add_argument("--cov-fail", type=int, help="Fail if coverage below threshold")
    
    # Code quality
    lint_group = parser.add_argument_group("Code Quality")
    lint_group.add_argument("--lint", action="store_true", help="Run all linting")
    lint_group.add_argument("--ruff", action="store_true", help="Run ruff linting")
    lint_group.add_argument("--pylint", action="store_true", help="Run pylint")
    lint_group.add_argument("--mypy", action="store_true", help="Run mypy type checking")
    lint_group.add_argument("--all-lint", action="store_true", help="Run all linters")
    lint_group.add_argument("--fix", action="store_true", help="Auto-fix linting issues")
    
    # Additional options
    parser.add_argument("--security", action="store_true", help="Run security checks")
    parser.add_argument("--report", action="store_true", help="Generate final report")
    parser.add_argument("--all", action="store_true", help="Run everything (tests, linting, security)")
    
    args = parser.parse_args()
    
    # Default behavior
    if not any([args.unit, args.integration, args.grpc, args.ui, args.i18n, args.metrics,
                args.lint, args.ruff, args.pylint, args.mypy, args.all_lint,
                args.security, args.all]):
        args.unit = True  # Default to unit tests
        args.coverage = True  # Default to coverage
    
    success = True
    
    # Run tests
    if args.all or not any([args.lint, args.ruff, args.pylint, args.mypy, args.all_lint, args.security]):
        success &= run_tests(args)
    
    # Run linting
    if args.lint or args.ruff or args.pylint or args.mypy or args.all_lint or args.all:
        success &= run_linting(args)
    
    # Run security checks
    if args.security or args.all:
        success &= run_security_checks()
    
    # Generate report
    if args.report or args.all:
        generate_report()
    
    if success:
        print(f"\n{'='*60}")
        print("✅ ALL CHECKS PASSED")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("❌ SOME CHECKS FAILED")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    sys.exit(main())