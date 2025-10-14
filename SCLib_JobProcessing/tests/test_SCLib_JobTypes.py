"""
Test cases for SC_JobTypes
Tests job type definitions, status transitions, and helper functions.
"""

import unittest
from datetime import datetime

from SCLib_JobTypes import (
    SC_JobType, SC_JobStatus, SC_DatasetStatus, SC_JOB_PRIORITY,
    SC_JOB_TYPE_CONFIGS, SC_DATASET_STATUS_TRANSITIONS,
    get_job_type_config, get_dataset_status_config,
    get_next_possible_states, is_valid_transition,
    get_job_type_for_status, is_terminal_status,
    get_status_description, get_job_type_description,
    LEGACY_STATUS_MAPPING, convert_legacy_status, convert_to_legacy_status
)


class TestSC_JobTypes(unittest.TestCase):
    """Test cases for SC_JobTypes."""
    
    def test_job_type_enum_values(self):
        """Test that job type enum has expected values."""
        expected_types = [
            'google_sync', 'dataset_conversion', 'file_upload',
            'file_extraction', 'data_compression', 'rsync_transfer',
            'backup_creation', 'data_validation'
        ]
        
        for job_type in expected_types:
            self.assertTrue(hasattr(SC_JobType, job_type.upper()))
            self.assertEqual(getattr(SC_JobType, job_type.upper()).value, job_type)
    
    def test_job_status_enum_values(self):
        """Test that job status enum has expected values."""
        expected_statuses = [
            'pending', 'running', 'completed', 'failed', 'retrying', 'cancelled'
        ]
        
        for status in expected_statuses:
            self.assertTrue(hasattr(SC_JobStatus, status.upper()))
            self.assertEqual(getattr(SC_JobStatus, status.upper()).value, status)
    
    def test_dataset_status_enum_values(self):
        """Test that dataset status enum has expected values."""
        expected_statuses = [
            'submitted', 'sync queued', 'syncing', 'conversion queued',
            'converting', 'upload queued', 'uploading', 'unzipping',
            'zipping', 'done', 'sync error', 'conversion error',
            'upload error', 'unzip error', 'compression error',
            'failed', 'retrying'
        ]
        
        for status in expected_statuses:
            # Convert spaces to underscores for enum attribute names
            attr_name = status.upper().replace(' ', '_')
            self.assertTrue(hasattr(SC_DatasetStatus, attr_name))
            self.assertEqual(getattr(SC_DatasetStatus, attr_name).value, status)
    
    def test_job_priority_values(self):
        """Test job priority values."""
        self.assertEqual(SC_JOB_PRIORITY['HIGH'], 1)
        self.assertEqual(SC_JOB_PRIORITY['NORMAL'], 2)
        self.assertEqual(SC_JOB_PRIORITY['LOW'], 3)
    
    def test_job_type_configs_completeness(self):
        """Test that all job types have configurations."""
        for job_type in SC_JobType:
            self.assertIn(job_type, SC_JOB_TYPE_CONFIGS)
            
            config = SC_JOB_TYPE_CONFIGS[job_type]
            required_fields = [
                'description', 'timeout_minutes', 'max_attempts',
                'requires_internet', 'priority', 'estimated_duration'
            ]
            
            for field in required_fields:
                self.assertIn(field, config)
    
    def test_dataset_status_transitions_completeness(self):
        """Test that all dataset statuses have transition configurations."""
        for status in SC_DatasetStatus:
            self.assertIn(status, SC_DATASET_STATUS_TRANSITIONS)
            
            config = SC_DATASET_STATUS_TRANSITIONS[status]
            required_fields = [
                'description', 'next_states', 'job_type', 'is_terminal'
            ]
            
            for field in required_fields:
                self.assertIn(field, config)
    
    def test_get_job_type_config(self):
        """Test getting job type configuration."""
        config = get_job_type_config(SC_JobType.DATASET_CONVERSION)
        
        self.assertIsInstance(config, dict)
        self.assertIn('description', config)
        self.assertIn('timeout_minutes', config)
        self.assertIn('max_attempts', config)
        self.assertIn('requires_internet', config)
        self.assertIn('priority', config)
        self.assertIn('estimated_duration', config)
        
        # Test specific values
        self.assertEqual(config['description'], 'Convert dataset to streamable format')
        self.assertEqual(config['timeout_minutes'], 120)
        self.assertEqual(config['max_attempts'], 2)
        self.assertFalse(config['requires_internet'])
        self.assertEqual(config['priority'], 1)
    
    def test_get_job_type_config_invalid(self):
        """Test getting job type configuration for invalid type."""
        # This should return empty dict for invalid type
        config = get_job_type_config('invalid_type')
        self.assertEqual(config, {})
    
    def test_get_dataset_status_config(self):
        """Test getting dataset status configuration."""
        config = get_dataset_status_config(SC_DatasetStatus.CONVERTING)
        
        self.assertIsInstance(config, dict)
        self.assertIn('description', config)
        self.assertIn('next_states', config)
        self.assertIn('job_type', config)
        self.assertIn('is_terminal', config)
        
        # Test specific values
        self.assertEqual(config['description'], 'Currently converting data')
        self.assertIn(SC_DatasetStatus.DONE, config['next_states'])
        self.assertIn(SC_DatasetStatus.CONVERSION_ERROR, config['next_states'])
        self.assertEqual(config['job_type'], SC_JobType.DATASET_CONVERSION)
        self.assertFalse(config['is_terminal'])
    
    def test_get_next_possible_states(self):
        """Test getting next possible states."""
        # Test submitted status
        next_states = get_next_possible_states(SC_DatasetStatus.SUBMITTED)
        expected_states = [
            SC_DatasetStatus.SYNC_QUEUED,
            SC_DatasetStatus.CONVERSION_QUEUED,
            SC_DatasetStatus.UPLOAD_QUEUED
        ]
        
        for state in expected_states:
            self.assertIn(state, next_states)
        
        # Test terminal status
        next_states = get_next_possible_states(SC_DatasetStatus.DONE)
        self.assertEqual(len(next_states), 0)
    
    def test_is_valid_transition(self):
        """Test transition validation."""
        # Valid transitions
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.SUBMITTED, SC_DatasetStatus.SYNC_QUEUED
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.SYNC_QUEUED, SC_DatasetStatus.SYNCING
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.CONVERTING, SC_DatasetStatus.DONE
        ))
        
        # Invalid transitions
        self.assertFalse(is_valid_transition(
            SC_DatasetStatus.SUBMITTED, SC_DatasetStatus.DONE
        ))
        self.assertFalse(is_valid_transition(
            SC_DatasetStatus.DONE, SC_DatasetStatus.SUBMITTED
        ))
        self.assertFalse(is_valid_transition(
            SC_DatasetStatus.SYNCING, SC_DatasetStatus.UPLOAD_QUEUED
        ))
    
    def test_get_job_type_for_status(self):
        """Test getting job type for status."""
        # Statuses with job types
        self.assertEqual(
            get_job_type_for_status(SC_DatasetStatus.SYNCING),
            SC_JobType.GOOGLE_SYNC
        )
        self.assertEqual(
            get_job_type_for_status(SC_DatasetStatus.CONVERTING),
            SC_JobType.DATASET_CONVERSION
        )
        self.assertEqual(
            get_job_type_for_status(SC_DatasetStatus.UPLOADING),
            SC_JobType.FILE_UPLOAD
        )
        self.assertEqual(
            get_job_type_for_status(SC_DatasetStatus.UNZIPPING),
            SC_JobType.FILE_EXTRACTION
        )
        self.assertEqual(
            get_job_type_for_status(SC_DatasetStatus.ZIPPING),
            SC_JobType.DATA_COMPRESSION
        )
        
        # Statuses without job types
        self.assertIsNone(get_job_type_for_status(SC_DatasetStatus.SUBMITTED))
        self.assertIsNone(get_job_type_for_status(SC_DatasetStatus.DONE))
        self.assertIsNone(get_job_type_for_status(SC_DatasetStatus.FAILED))
    
    def test_is_terminal_status(self):
        """Test terminal status detection."""
        # Terminal statuses
        self.assertTrue(is_terminal_status(SC_DatasetStatus.DONE))
        self.assertTrue(is_terminal_status(SC_DatasetStatus.FAILED))
        
        # Non-terminal statuses
        self.assertFalse(is_terminal_status(SC_DatasetStatus.SUBMITTED))
        self.assertFalse(is_terminal_status(SC_DatasetStatus.SYNCING))
        self.assertFalse(is_terminal_status(SC_DatasetStatus.CONVERTING))
        self.assertFalse(is_terminal_status(SC_DatasetStatus.RETRYING))
    
    def test_get_status_description(self):
        """Test getting status descriptions."""
        self.assertEqual(
            get_status_description(SC_DatasetStatus.SUBMITTED),
            'Dataset submitted, waiting for processing'
        )
        self.assertEqual(
            get_status_description(SC_DatasetStatus.CONVERTING),
            'Currently converting data'
        )
        self.assertEqual(
            get_status_description(SC_DatasetStatus.DONE),
            'Processing completed successfully'
        )
    
    def test_get_job_type_description(self):
        """Test getting job type descriptions."""
        self.assertEqual(
            get_job_type_description(SC_JobType.GOOGLE_SYNC),
            'Synchronize data from Google Drive'
        )
        self.assertEqual(
            get_job_type_description(SC_JobType.DATASET_CONVERSION),
            'Convert dataset to streamable format'
        )
        self.assertEqual(
            get_job_type_description(SC_JobType.FILE_UPLOAD),
            'Upload files to storage'
        )
    
    def test_legacy_status_mapping_completeness(self):
        """Test that legacy status mapping is complete."""
        expected_legacy_statuses = [
            'submitted', 'sync queued', 'syncing', 'conversion queued',
            'converting', 'upload queued', 'uploading', 'unzipping',
            'zipping', 'done', 'sync error', 'conversion error',
            'upload error', 'unzip error', 'compression error',
            'failed', 'retrying'
        ]
        
        for status in expected_legacy_statuses:
            self.assertIn(status, LEGACY_STATUS_MAPPING)
    
    def test_convert_legacy_status(self):
        """Test converting legacy status to enum."""
        # Test valid conversions
        self.assertEqual(
            convert_legacy_status('submitted'),
            SC_DatasetStatus.SUBMITTED
        )
        self.assertEqual(
            convert_legacy_status('sync queued'),
            SC_DatasetStatus.SYNC_QUEUED
        )
        self.assertEqual(
            convert_legacy_status('syncing'),
            SC_DatasetStatus.SYNCING
        )
        self.assertEqual(
            convert_legacy_status('conversion queued'),
            SC_DatasetStatus.CONVERSION_QUEUED
        )
        self.assertEqual(
            convert_legacy_status('converting'),
            SC_DatasetStatus.CONVERTING
        )
        self.assertEqual(
            convert_legacy_status('done'),
            SC_DatasetStatus.DONE
        )
        self.assertEqual(
            convert_legacy_status('failed'),
            SC_DatasetStatus.FAILED
        )
        
        # Test invalid conversion (should default to submitted)
        self.assertEqual(
            convert_legacy_status('invalid_status'),
            SC_DatasetStatus.SUBMITTED
        )
    
    def test_convert_to_legacy_status(self):
        """Test converting enum status to legacy string."""
        # Test valid conversions
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.SUBMITTED),
            'submitted'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.SYNC_QUEUED),
            'sync queued'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.SYNCING),
            'syncing'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.CONVERSION_QUEUED),
            'conversion queued'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.CONVERTING),
            'converting'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.DONE),
            'done'
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.FAILED),
            'failed'
        )
    
    def test_job_type_config_values(self):
        """Test specific job type configuration values."""
        # Test Google Sync configuration
        google_sync_config = SC_JOB_TYPE_CONFIGS[SC_JobType.GOOGLE_SYNC]
        self.assertEqual(google_sync_config['timeout_minutes'], 60)
        self.assertEqual(google_sync_config['max_attempts'], 3)
        self.assertTrue(google_sync_config['requires_internet'])
        self.assertEqual(google_sync_config['priority'], 2)
        
        # Test Dataset Conversion configuration
        conversion_config = SC_JOB_TYPE_CONFIGS[SC_JobType.DATASET_CONVERSION]
        self.assertEqual(conversion_config['timeout_minutes'], 120)
        self.assertEqual(conversion_config['max_attempts'], 2)
        self.assertFalse(conversion_config['requires_internet'])
        self.assertEqual(conversion_config['priority'], 1)
        
        # Test File Upload configuration
        upload_config = SC_JOB_TYPE_CONFIGS[SC_JobType.FILE_UPLOAD]
        self.assertEqual(upload_config['timeout_minutes'], 30)
        self.assertEqual(upload_config['max_attempts'], 5)
        self.assertTrue(upload_config['requires_internet'])
        self.assertEqual(upload_config['priority'], 2)
    
    def test_dataset_status_transition_logic(self):
        """Test dataset status transition logic."""
        # Test submitted status transitions
        submitted_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.SUBMITTED]
        self.assertIn(SC_DatasetStatus.SYNC_QUEUED, submitted_config['next_states'])
        self.assertIn(SC_DatasetStatus.CONVERSION_QUEUED, submitted_config['next_states'])
        self.assertIn(SC_DatasetStatus.UPLOAD_QUEUED, submitted_config['next_states'])
        self.assertIsNone(submitted_config['job_type'])
        self.assertFalse(submitted_config['is_terminal'])
        
        # Test syncing status transitions
        syncing_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.SYNCING]
        self.assertIn(SC_DatasetStatus.CONVERSION_QUEUED, syncing_config['next_states'])
        self.assertIn(SC_DatasetStatus.SYNC_ERROR, syncing_config['next_states'])
        self.assertEqual(syncing_config['job_type'], SC_JobType.GOOGLE_SYNC)
        self.assertFalse(syncing_config['is_terminal'])
        
        # Test done status (terminal)
        done_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.DONE]
        self.assertEqual(len(done_config['next_states']), 0)
        self.assertIsNone(done_config['job_type'])
        self.assertTrue(done_config['is_terminal'])
        
        # Test failed status (terminal)
        failed_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.FAILED]
        self.assertEqual(len(failed_config['next_states']), 0)
        self.assertIsNone(failed_config['job_type'])
        self.assertTrue(failed_config['is_terminal'])
    
    def test_error_status_transitions(self):
        """Test error status transitions."""
        # Test sync error transitions
        sync_error_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.SYNC_ERROR]
        self.assertIn(SC_DatasetStatus.SYNC_QUEUED, sync_error_config['next_states'])
        self.assertIn(SC_DatasetStatus.FAILED, sync_error_config['next_states'])
        self.assertEqual(sync_error_config['job_type'], SC_JobType.GOOGLE_SYNC)
        self.assertFalse(sync_error_config['is_terminal'])
        
        # Test conversion error transitions
        conversion_error_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.CONVERSION_ERROR]
        self.assertIn(SC_DatasetStatus.CONVERSION_QUEUED, conversion_error_config['next_states'])
        self.assertIn(SC_DatasetStatus.FAILED, conversion_error_config['next_states'])
        self.assertEqual(conversion_error_config['job_type'], SC_JobType.DATASET_CONVERSION)
        self.assertFalse(conversion_error_config['is_terminal'])
        
        # Test upload error transitions
        upload_error_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.UPLOAD_ERROR]
        self.assertIn(SC_DatasetStatus.UPLOAD_QUEUED, upload_error_config['next_states'])
        self.assertIn(SC_DatasetStatus.FAILED, upload_error_config['next_states'])
        self.assertEqual(upload_error_config['job_type'], SC_JobType.FILE_UPLOAD)
        self.assertFalse(upload_error_config['is_terminal'])
    
    def test_retrying_status_transitions(self):
        """Test retrying status transitions."""
        retrying_config = SC_DATASET_STATUS_TRANSITIONS[SC_DatasetStatus.RETRYING]
        self.assertIn(SC_DatasetStatus.SYNC_QUEUED, retrying_config['next_states'])
        self.assertIn(SC_DatasetStatus.CONVERSION_QUEUED, retrying_config['next_states'])
        self.assertIn(SC_DatasetStatus.UPLOAD_QUEUED, retrying_config['next_states'])
        self.assertIsNone(retrying_config['job_type'])
        self.assertFalse(retrying_config['is_terminal'])


if __name__ == '__main__':
    unittest.main()
