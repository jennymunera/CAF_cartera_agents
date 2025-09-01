#!/usr/bin/env python3
"""
Test script for the CrewAI + Docling Analysis System

This script helps test the complete workflow:
1. Document processing with Docling
2. Multi-agent analysis with CrewAI
3. Results generation and export

Usage:
    python test_system.py
"""

import os
import sys

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from main import main, run_full_analysis
except ImportError:
    # If main import fails, we'll handle it gracefully
    main = None
    run_full_analysis = None
    
from config.settings import settings as config

def test_configuration():
    """Test system configuration."""
    print("Testing System Configuration")
    print("=" * 40)
    
    try:
        config.validate_config()
        print("[OK] Configuration is valid")
        
        # Test LLM configuration
        llm_config = config.get_llm_config()
        print(f"[OK] LLM configured: {llm_config.get('model', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        print("\nPlease check:")
        print("  1. .env file exists with OPENAI_API_KEY")
        print("  2. Azure OpenAI credentials are correct")
        print("  3. All required environment variables are set")
        return False

def test_directory_structure():
    """Test required directory structure."""
    print("\nTesting Directory Structure")
    print("=" * 40)
    
    required_dirs = [
        'input_docs',
        'output_docs',
        'agents',
        'tasks',
        'config'
    ]
    
    required_files = [
        'main.py',
        'docling_processor.py',
        'agents/agents.py',
        'tasks/task.py',
        'config/settings.py'
    ]
    
    all_good = True
    
    # Check directories
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"[OK] Directory exists: {dir_name}")
        else:
            print(f"[ERROR] Missing directory: {dir_name}")
            all_good = False
    
    # Check files
    for file_name in required_files:
        if os.path.exists(file_name):
            print(f"[OK] File exists: {file_name}")
        else:
            print(f"[ERROR] Missing file: {file_name}")
            all_good = False
    
    return all_good

def test_imports():
    """Test all required imports."""
    print("\nTesting Imports")
    print("=" * 40)
    
    try:
        # Test CrewAI imports
        from crewai import Agent, Task, Crew, Process
        print("[OK] CrewAI imports successful")
        
        # Test agent imports
        from agents.agents import (
            agente_auditorias,
            agente_productos,
            agente_desembolsos,
            agente_experto_auditorias,
            agente_experto_productos,
            agente_experto_desembolsos,
            agente_concatenador
        )
        print("[OK] Agent imports successful")
        
        # Test task imports
        from tasks.task import (
            task_auditorias,
            task_productos,
            task_desembolsos,
            task_experto_auditorias,
            task_experto_productos,
            task_experto_desembolsos,
            task_concatenador
        )
        print("[OK] Task imports successful")
        
        # Test Docling imports
        from docling_processor import process_documents, DoclingProcessor
        print("[OK] Docling processor import successful")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("\nPlease install missing dependencies:")
        print("  pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

def run_system_test():
    """Run complete system test."""
    print("CrewAI + Docling System Test")
    print("=" * 50)
    
    # Run all tests
    tests = [
        ("Configuration", test_configuration),
        ("Directory Structure", test_directory_structure),
        ("Imports", test_imports)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] {test_name} test failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\nTest Summary")
    print("=" * 20)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! System is ready.")
        print("\nNext steps:")
        print("  1. Place PDF files in 'input_docs/project_name/'")
        print("  2. Run: python -c 'from main import run_full_analysis; run_full_analysis(\"project_name\")'")
    else:
        print("\n[ERROR] Some tests failed. Please fix the issues above.")
    
    return all_passed

if __name__ == "__main__":
    # Run system test
    success = run_system_test()
    
    if success:
        print("\n" + "=" * 50)
        print("Running main() to show available projects...")
        print("=" * 50)
        
        try:
            main()
        except Exception as e:
            print(f"Error running main(): {e}")
            import traceback
            traceback.print_exc()
    
    sys.exit(0 if success else 1)