#!/usr/bin/env python3
"""
Test runner script for CrewAI + Docling Analysis System

This script provides different ways to run the test suite:
- All tests
- Unit tests only
- Integration tests only
- Specific test categories
- With coverage reporting

Usage:
    python run_tests.py [options]

Options:
    --unit          Run only unit tests
    --integration   Run only integration tests
    --docling       Run only Docling-related tests
    --crewai        Run only CrewAI-related tests
    --coverage      Run with coverage reporting
    --verbose       Verbose output
    --fast          Skip slow tests
    --parallel      Run tests in parallel
    --help          Show this help message
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle errors."""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def install_dependencies():
    """Install test dependencies."""
    print("Installing test dependencies...")
    return run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "Installing dependencies"
    )


def run_unit_tests(verbose=False, coverage=False, parallel=False):
    """Run unit tests only."""
    cmd = [sys.executable, "-m", "pytest", "-m", "unit"]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
    if parallel:
        cmd.extend(["-n", "auto"])
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False, coverage=False, parallel=False):
    """Run integration tests only."""
    cmd = [sys.executable, "-m", "pytest", "-m", "integration"]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])
    if parallel:
        cmd.extend(["-n", "auto"])
    
    return run_command(cmd, "Integration Tests")


def run_docling_tests(verbose=False, coverage=False, parallel=False):
    """Run Docling-specific tests."""
    cmd = [sys.executable, "-m", "pytest", "-m", "docling"]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=docling_processor", "--cov-report=html", "--cov-report=term"])
    if parallel:
        cmd.extend(["-n", "auto"])
    
    return run_command(cmd, "Docling Tests")


def run_crewai_tests(verbose=False, coverage=False, parallel=False):
    """Run CrewAI-specific tests."""
    cmd = [sys.executable, "-m", "pytest", "-m", "crewai"]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=agents", "--cov=tasks", "--cov-report=html", "--cov-report=term"])
    if parallel:
        cmd.extend(["-n", "auto"])
    
    return run_command(cmd, "CrewAI Tests")


def run_all_tests(verbose=False, coverage=False, parallel=False, fast=False):
    """Run all tests."""
    cmd = [sys.executable, "-m", "pytest", "test/"]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    if parallel:
        cmd.extend(["-n", "auto"])
    if fast:
        cmd.extend(["-m", "not slow"])
    
    return run_command(cmd, "All Tests")


def run_specific_test(test_path, verbose=False, coverage=False):
    """Run a specific test file or test function."""
    cmd = [sys.executable, "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term"])
    
    return run_command(cmd, f"Specific Test: {test_path}")


def generate_coverage_report():
    """Generate detailed coverage report."""
    print("\nGenerating coverage report...")
    
    # Generate HTML report
    run_command(
        [sys.executable, "-m", "coverage", "html"],
        "HTML Coverage Report"
    )
    
    # Generate XML report for CI/CD
    run_command(
        [sys.executable, "-m", "coverage", "xml"],
        "XML Coverage Report"
    )
    
    print("\nCoverage reports generated:")
    print("- HTML: htmlcov/index.html")
    print("- XML: coverage.xml")


def lint_code():
    """Run code linting."""
    print("\nRunning code linting...")
    
    # Run flake8
    flake8_success = run_command(
        [sys.executable, "-m", "flake8", ".", "--exclude=venv,env,__pycache__,.git"],
        "Flake8 Linting"
    )
    
    # Run black check
    black_success = run_command(
        [sys.executable, "-m", "black", "--check", "."],
        "Black Code Formatting Check"
    )
    
    return flake8_success and black_success


def format_code():
    """Format code with black."""
    return run_command(
        [sys.executable, "-m", "black", "."],
        "Code Formatting with Black"
    )


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Test runner for CrewAI + Docling Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--docling", action="store_true", help="Run only Docling tests")
    parser.add_argument("--crewai", action="store_true", help="Run only CrewAI tests")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--install", action="store_true", help="Install dependencies first")
    parser.add_argument("--lint", action="store_true", help="Run code linting")
    parser.add_argument("--format", action="store_true", help="Format code with black")
    parser.add_argument("--test", type=str, help="Run specific test file or function")
    
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    success = True
    
    # Install dependencies if requested
    if args.install:
        if not install_dependencies():
            print("Failed to install dependencies")
            return 1
    
    # Format code if requested
    if args.format:
        if not format_code():
            success = False
    
    # Run linting if requested
    if args.lint:
        if not lint_code():
            success = False
    
    # Run specific test
    if args.test:
        if not run_specific_test(args.test, args.verbose, args.coverage):
            success = False
    # Run test categories
    elif args.unit:
        if not run_unit_tests(args.verbose, args.coverage, args.parallel):
            success = False
    elif args.integration:
        if not run_integration_tests(args.verbose, args.coverage, args.parallel):
            success = False
    elif args.docling:
        if not run_docling_tests(args.verbose, args.coverage, args.parallel):
            success = False
    elif args.crewai:
        if not run_crewai_tests(args.verbose, args.coverage, args.parallel):
            success = False
    else:
        # Run all tests by default
        if not run_all_tests(args.verbose, args.coverage, args.parallel, args.fast):
            success = False
    
    # Generate coverage report if requested
    if args.coverage:
        generate_coverage_report()
    
    if success:
        print("\n[SUCCESS] All tests completed successfully!")
        return 0
    else:
        print("\n[ERROR] Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())