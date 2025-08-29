"""
Test runner script for comprehensive test execution.
"""
import pytest
import sys
import os
from pathlib import Path


def run_unit_tests():
    """Run all unit tests."""
    print("Running unit tests...")
    return pytest.main([
        "tests/test_auth.py",
        "tests/test_billing.py",
        "tests/test_video_processor.py",
        "tests/test_transcription.py",
        "tests/test_diarization.py",
        "tests/test_text_processing.py",
        "tests/test_keyframe_extraction.py",
        "tests/test_visual_analysis.py",
        "tests/test_gpt_visual_analysis.py",
        "tests/test_dialogue_mapping.py",
        "tests/test_music_detection.py",
        "tests/test_montage_table.py",
        "tests/test_docx_generator.py",
        "tests/test_upload.py",
        "tests/test_payments.py",
        "tests/test_task_queue.py",
        "tests/test_pipeline_orchestrator.py",
        "tests/test_fallback_integration.py",
        "tests/test_error_handling.py",
        "tests/test_comprehensive_services.py",
        "-v",
        "--tb=short"
    ])


def run_integration_tests():
    """Run integration tests."""
    print("Running integration tests...")
    return pytest.main([
        "tests/test_api_core.py",
        "tests/test_api_projects.py",
        "tests/test_video_integration.py",
        "tests/test_end_to_end_workflows.py",
        "-v",
        "--tb=short"
    ])


def run_performance_tests():
    """Run performance and load tests."""
    print("Running performance tests...")
    return pytest.main([
        "tests/test_performance_and_load.py",
        "-v",
        "--tb=short",
        "-s"  # Don't capture output for performance metrics
    ])


def run_simple_tests():
    """Run simplified test versions for quick validation."""
    print("Running simple tests...")
    return pytest.main([
        "tests/test_api_core_simple.py",
        "tests/test_api_projects_simple.py",
        "tests/test_task_queue_simple.py",
        "-v",
        "--tb=short"
    ])


def run_all_tests():
    """Run all tests in sequence."""
    print("Running complete test suite...")
    
    # Run unit tests first
    unit_result = run_unit_tests()
    if unit_result != 0:
        print("Unit tests failed!")
        return unit_result
    
    # Run integration tests
    integration_result = run_integration_tests()
    if integration_result != 0:
        print("Integration tests failed!")
        return integration_result
    
    # Run performance tests (non-blocking)
    print("Running performance tests (warnings only)...")
    performance_result = run_performance_tests()
    if performance_result != 0:
        print("Performance tests had issues (continuing...)")
    
    print("All critical tests passed!")
    return 0


def run_coverage_report():
    """Run tests with coverage reporting."""
    print("Running tests with coverage...")
    return pytest.main([
        "--cov=app",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-fail-under=80",
        "tests/",
        "-v"
    ])


def main():
    """Main test runner function."""
    if len(sys.argv) < 2:
        print("Usage: python test_runner.py [unit|integration|performance|simple|all|coverage]")
        sys.exit(1)
    
    test_type = sys.argv[1].lower()
    
    # Set up test environment
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = "sqlite:///./test_filmlist.db"
    
    if test_type == "unit":
        result = run_unit_tests()
    elif test_type == "integration":
        result = run_integration_tests()
    elif test_type == "performance":
        result = run_performance_tests()
    elif test_type == "simple":
        result = run_simple_tests()
    elif test_type == "all":
        result = run_all_tests()
    elif test_type == "coverage":
        result = run_coverage_report()
    else:
        print(f"Unknown test type: {test_type}")
        print("Available types: unit, integration, performance, simple, all, coverage")
        sys.exit(1)
    
    sys.exit(result)


if __name__ == "__main__":
    main()