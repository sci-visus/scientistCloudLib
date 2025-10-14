#!/usr/bin/env python3
"""
Test runner for SC_JobProcessing system
Runs all test suites and provides comprehensive test coverage.
"""

import unittest
import sys
import os
import time
from io import StringIO

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all test modules
from test_SCLib_JobQueueManager import TestSCLib_JobQueueManager
from test_SCLib_BackgroundService import TestSCLib_BackgroundService
from test_SCLib_JobTypes import TestSCLib_JobTypes
from test_SCLib_JobMonitor import TestSCLib_JobMonitor
from test_SCLib_JobMigration import TestSCLib_JobMigration
from test_SCLib_UploadJobTypes import TestSC_UploadJobTypes
from test_SCLib_UploadProcessor import TestSCLib_UploadProcessor
from test_SCLib_UploadAPI import TestSC_UploadAPI
from test_integration import TestSC_JobProcessingIntegration

# Import FastAPI test modules
try:
    from test_SCLib_UploadAPI_FastAPI import TestSCLib_UploadAPI_FastAPI
    from test_SCLib_UploadAPI_LargeFiles import TestSCLib_UploadAPI_LargeFiles
    from test_SCLib_UploadClient_FastAPI import TestScientistCloudUploadClient, TestAsyncScientistCloudUploadClient
    from test_SCLib_UploadClient_LargeFiles import TestLargeFileUploadClient, TestAsyncLargeFileUploadClient
    from test_integration_large_files import TestLargeFileIntegration
    FASTAPI_TESTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: FastAPI tests not available: {e}")
    FASTAPI_TESTS_AVAILABLE = False


def run_test_suite(test_class, suite_name):
    """Run a specific test suite and return results."""
    print(f"\n{'='*60}")
    print(f"Running {suite_name}")
    print(f"{'='*60}")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    
    # Run tests with detailed output
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        descriptions=True,
        failfast=False
    )
    
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    # Print results
    output = stream.getvalue()
    print(output)
    
    # Print summary
    print(f"\n{suite_name} Summary:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    print(f"  Time: {end_time - start_time:.2f} seconds")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            error_msg = traceback.split('AssertionError: ')[-1].split('\n')[0]
            print(f"  - {test}: {error_msg}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            error_msg = traceback.split('\n')[-2]
            print(f"  - {test}: {error_msg}")
    
    return result


def run_all_tests():
    """Run all test suites."""
    print("SC_JobProcessing System Test Suite")
    print("=" * 60)
    
    # Define test suites
    test_suites = [
        (TestSCLib_JobTypes, "SC_JobTypes Tests"),
        (TestSCLib_JobQueueManager, "SC_JobQueueManager Tests"),
        (TestSCLib_BackgroundService, "SC_BackgroundService Tests"),
        (TestSCLib_JobMonitor, "SC_JobMonitor Tests"),
        (TestSCLib_JobMigration, "SC_JobMigration Tests"),
        (TestSC_UploadJobTypes, "SC_UploadJobTypes Tests"),
        (TestSCLib_UploadProcessor, "SC_UploadProcessor Tests"),
        (TestSC_UploadAPI, "SC_UploadAPI Tests (Legacy Flask)"),
        (TestSC_JobProcessingIntegration, "Integration Tests")
    ]
    
    # Add FastAPI test suites if available
    if FASTAPI_TESTS_AVAILABLE:
        test_suites.extend([
            (TestSCLib_UploadAPI_FastAPI, "SC_UploadAPI FastAPI Tests"),
            (TestSCLib_UploadAPI_LargeFiles, "SC_UploadAPI Large Files Tests"),
            (TestScientistCloudUploadClient, "SC_UploadClient FastAPI Tests"),
            (TestAsyncScientistCloudUploadClient, "SC_UploadClient Async Tests"),
            (TestLargeFileUploadClient, "SC_LargeFileUploadClient Tests"),
            (TestAsyncLargeFileUploadClient, "SC_LargeFileUploadClient Async Tests"),
            (TestLargeFileIntegration, "Large File Integration Tests")
        ])
    
    # Run all test suites
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_time = 0
    
    for test_class, suite_name in test_suites:
        result = run_test_suite(test_class, suite_name)
        
        total_tests += result.testsRun
        total_failures += len(result.failures)
        total_errors += len(result.errors)
    
    # Print overall summary
    print(f"\n{'='*60}")
    print("OVERALL TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests: {total_tests}")
    print(f"Total Failures: {total_failures}")
    print(f"Total Errors: {total_errors}")
    print(f"Success Rate: {((total_tests - total_failures - total_errors) / total_tests * 100):.1f}%")
    
    if total_failures == 0 and total_errors == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total_failures + total_errors} test(s) failed")
        return 1


def run_specific_tests(test_names):
    """Run specific test suites."""
    print("SC_JobProcessing System - Specific Tests")
    print("=" * 60)
    
    # Map test names to test classes
    test_map = {
        'types': (TestSCLib_JobTypes, "SC_JobTypes Tests"),
        'queue': (TestSCLib_JobQueueManager, "SC_JobQueueManager Tests"),
        'service': (TestSCLib_BackgroundService, "SC_BackgroundService Tests"),
        'monitor': (TestSCLib_JobMonitor, "SC_JobMonitor Tests"),
        'migration': (TestSCLib_JobMigration, "SC_JobMigration Tests"),
        'upload_types': (TestSC_UploadJobTypes, "SC_UploadJobTypes Tests"),
        'upload_processor': (TestSCLib_UploadProcessor, "SC_UploadProcessor Tests"),
        'upload_api': (TestSC_UploadAPI, "SC_UploadAPI Tests (Legacy Flask)"),
        'integration': (TestSC_JobProcessingIntegration, "Integration Tests")
    }
    
    # Add FastAPI test mappings if available
    if FASTAPI_TESTS_AVAILABLE:
        test_map.update({
            'fastapi_api': (TestSCLib_UploadAPI_FastAPI, "SC_UploadAPI FastAPI Tests"),
            'large_files_api': (TestSCLib_UploadAPI_LargeFiles, "SC_UploadAPI Large Files Tests"),
            'fastapi_client': (TestScientistCloudUploadClient, "SC_UploadClient FastAPI Tests"),
            'async_client': (TestAsyncScientistCloudUploadClient, "SC_UploadClient Async Tests"),
            'large_files_client': (TestLargeFileUploadClient, "SC_LargeFileUploadClient Tests"),
            'async_large_client': (TestAsyncLargeFileUploadClient, "SC_LargeFileUploadClient Async Tests"),
            'large_files_integration': (TestLargeFileIntegration, "Large File Integration Tests")
        })
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    
    for test_name in test_names:
        if test_name in test_map:
            test_class, suite_name = test_map[test_name]
            result = run_test_suite(test_class, suite_name)
            
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
        else:
            print(f"\nUnknown test suite: {test_name}")
            print(f"Available suites: {', '.join(test_map.keys())}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests: {total_tests}")
    print(f"Total Failures: {total_failures}")
    print(f"Total Errors: {total_errors}")
    
    if total_failures == 0 and total_errors == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total_failures + total_errors} test(s) failed")
        return 1


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run specific tests
        test_names = sys.argv[1:]
        return run_specific_tests(test_names)
    else:
        # Run all tests
        return run_all_tests()


if __name__ == '__main__':
    sys.exit(main())
