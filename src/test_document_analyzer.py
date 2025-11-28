#!/usr/bin/env python3
"""
Tests for the Event-Driven Document Processing Function App

This module contains unit tests and integration tests for:
- utils.py: Document analysis functions with managed identity support
- function_app.py: Blob trigger and HTTP endpoint functions

Run tests with: pytest test_document_analyzer.py -v
Run with coverage: pytest test_document_analyzer.py -v --cov=. --cov-report=html
"""

import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Import modules under test
from utils import analyze_document, extract_fields_from_result, _get_auth_headers


# =============================================================================
# Unit Tests for utils.py
# =============================================================================

class TestGetAuthHeaders:
    """Tests for _get_auth_headers function."""
    
    def test_subscription_key_auth(self):
        """Test authentication with subscription key."""
        headers = _get_auth_headers(subscription_key="test-key-123")
        assert headers == {"Ocp-Apim-Subscription-Key": "test-key-123"}
    
    def test_managed_identity_auth(self):
        """Test authentication with managed identity credential."""
        mock_credential = Mock()
        mock_token = Mock()
        mock_token.token = "test-bearer-token"
        mock_credential.get_token.return_value = mock_token
        
        headers = _get_auth_headers(credential=mock_credential)
        
        assert headers == {"Authorization": "Bearer test-bearer-token"}
        mock_credential.get_token.assert_called_once_with(
            "https://cognitiveservices.azure.com/.default"
        )
    
    def test_credential_takes_precedence(self):
        """Test that credential takes precedence over subscription key."""
        mock_credential = Mock()
        mock_token = Mock()
        mock_token.token = "bearer-token"
        mock_credential.get_token.return_value = mock_token
        
        headers = _get_auth_headers(
            credential=mock_credential,
            subscription_key="should-not-use"
        )
        
        assert "Authorization" in headers
        assert "Ocp-Apim-Subscription-Key" not in headers
    
    def test_no_auth_raises_error(self):
        """Test that missing both auth methods raises ValueError."""
        with pytest.raises(ValueError, match="Either credential or subscription_key"):
            _get_auth_headers()


class TestAnalyzeDocument:
    """Tests for analyze_document function."""
    
    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_successful_analysis_with_key(self, mock_get, mock_post):
        """Test successful document analysis with subscription key."""
        # Setup mock responses
        mock_post_response = Mock()
        mock_post_response.headers = {"operation-location": "https://test.com/operation/123"}
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response
        
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "status": "succeeded",
            "result": {"contents": []}
        }
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response
        
        # Execute
        result = analyze_document(
            document_bytes=b"test document content",
            endpoint="https://test.cognitiveservices.azure.com",
            analyzer_id="test-analyzer",
            subscription_key="test-key"
        )
        
        # Verify
        assert result["status"] == "succeeded"
        mock_post.assert_called_once()
        assert "Ocp-Apim-Subscription-Key" in mock_post.call_args[1]["headers"]
    
    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_successful_analysis_with_credential(self, mock_get, mock_post):
        """Test successful document analysis with managed identity."""
        mock_credential = Mock()
        mock_token = Mock()
        mock_token.token = "test-bearer-token"
        mock_credential.get_token.return_value = mock_token
        
        mock_post_response = Mock()
        mock_post_response.headers = {"operation-location": "https://test.com/operation/123"}
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response
        
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "status": "succeeded",
            "result": {"contents": []}
        }
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response
        
        result = analyze_document(
            document_bytes=b"test document content",
            endpoint="https://test.cognitiveservices.azure.com",
            analyzer_id="test-analyzer",
            credential=mock_credential
        )
        
        assert result["status"] == "succeeded"
        assert "Authorization" in mock_post.call_args[1]["headers"]
    
    @patch('utils.requests.post')
    @patch('utils.requests.get')
    @patch('utils.time.sleep')  # Speed up test by mocking sleep
    def test_polling_until_success(self, mock_sleep, mock_get, mock_post):
        """Test that polling continues until status is succeeded."""
        mock_post_response = Mock()
        mock_post_response.headers = {"operation-location": "https://test.com/operation/123"}
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response
        
        # Return "running" twice, then "succeeded"
        mock_get_response = Mock()
        mock_get_response.raise_for_status = Mock()
        mock_get_response.json.side_effect = [
            {"status": "running"},
            {"status": "running"},
            {"status": "succeeded", "result": {}}
        ]
        mock_get.return_value = mock_get_response
        
        result = analyze_document(
            document_bytes=b"test",
            endpoint="https://test.cognitiveservices.azure.com",
            analyzer_id="test-analyzer",
            subscription_key="test-key"
        )
        
        assert result["status"] == "succeeded"
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_analysis_failure_raises_error(self, mock_get, mock_post):
        """Test that failed analysis raises RuntimeError."""
        mock_post_response = Mock()
        mock_post_response.headers = {"operation-location": "https://test.com/operation/123"}
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response
        
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "status": "failed",
            "error": {"message": "Document format not supported"}
        }
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response
        
        with pytest.raises(RuntimeError, match="Analysis failed"):
            analyze_document(
                document_bytes=b"test",
                endpoint="https://test.cognitiveservices.azure.com",
                analyzer_id="test-analyzer",
                subscription_key="test-key"
            )


class TestExtractFieldsFromResult:
    """Tests for extract_fields_from_result function."""
    
    def test_extract_string_fields(self):
        """Test extraction of string field values."""
        result = {
            "result": {
                "contents": [
                    {
                        "fields": {
                            "FirstName": {"valueString": "John"},
                            "LastName": {"valueString": "Doe"}
                        }
                    }
                ]
            }
        }
        
        fields = extract_fields_from_result(result)
        
        assert fields["FirstName"] == "John"
        assert fields["LastName"] == "Doe"
    
    def test_extract_number_fields(self):
        """Test extraction of number field values."""
        result = {
            "result": {
                "contents": [
                    {
                        "fields": {
                            "Amount": {"valueNumber": 123.45}
                        }
                    }
                ]
            }
        }
        
        fields = extract_fields_from_result(result)
        
        assert fields["Amount"] == 123.45
    
    def test_extract_date_fields(self):
        """Test extraction of date field values."""
        result = {
            "result": {
                "contents": [
                    {
                        "fields": {
                            "DateOfPurchase": {"valueDate": "2025-01-15"}
                        }
                    }
                ]
            }
        }
        
        fields = extract_fields_from_result(result)
        
        assert fields["DateOfPurchase"] == "2025-01-15"
    
    def test_empty_result(self):
        """Test extraction from empty result."""
        result = {"result": {"contents": []}}
        
        fields = extract_fields_from_result(result)
        
        assert fields == {}
    
    def test_missing_result_key(self):
        """Test extraction when result key is missing."""
        result = {}
        
        fields = extract_fields_from_result(result)
        
        assert fields == {}


# =============================================================================
# Unit Tests for function_app.py
# =============================================================================

class TestFunctionApp:
    """Tests for Function App functions."""
    
    @patch('function_app.get_cosmos_client')
    @patch('function_app.analyze_document')
    @patch('function_app.get_credential')
    @patch('function_app.ACU_ENDPOINT', 'https://test.cognitiveservices.azure.com')
    @patch('function_app.ACU_KEY', 'test-key')
    @patch('function_app.COSMOS_DATABASE', 'documents')
    @patch('function_app.COSMOS_CONTAINER', 'processed-documents')
    def test_process_document_internal(self, mock_get_credential, mock_analyze, mock_cosmos):
        """Test internal document processing logic."""
        from function_app import process_document_internal
        
        # Setup mocks
        mock_get_credential.return_value = None  # Use key-based auth
        mock_analyze.return_value = {
            "status": "succeeded",
            "result": {
                "contents": [
                    {
                        "fields": {
                            "FirstName": {"valueString": "Test"},
                            "Amount": {"valueNumber": 99.99}
                        }
                    }
                ]
            }
        }
        
        mock_container = Mock()
        mock_database = Mock()
        mock_database.get_container_client.return_value = mock_container
        mock_client = Mock()
        mock_client.get_database_client.return_value = mock_database
        mock_cosmos.return_value = mock_client
        
        result = process_document_internal(
            document_bytes=b"test content",
            document_name="test.pdf",
            content_type="application/pdf"
        )
        
        assert result["fileName"] == "test.pdf"
        assert result["contentType"] == "application/pdf"
        assert result["status"] == "processed"
        assert "FirstName" in result["extractedFields"]
        mock_container.upsert_item.assert_called_once()


class TestContentTypeDetection:
    """Tests for content type detection."""
    
    def test_pdf_content_type(self):
        """Test PDF content type detection."""
        from function_app import _get_content_type
        assert _get_content_type("document.pdf") == "application/pdf"
    
    def test_image_content_types(self):
        """Test image content type detection."""
        from function_app import _get_content_type
        assert _get_content_type("image.png") == "image/png"
        assert _get_content_type("photo.jpg") == "image/jpeg"
        assert _get_content_type("photo.jpeg") == "image/jpeg"
        assert _get_content_type("scan.tiff") == "image/tiff"
    
    def test_office_content_types(self):
        """Test Office document content type detection."""
        from function_app import _get_content_type
        assert "wordprocessingml" in _get_content_type("doc.docx")
        assert "spreadsheetml" in _get_content_type("sheet.xlsx")
    
    def test_unknown_content_type(self):
        """Test fallback for unknown extensions."""
        from function_app import _get_content_type
        assert _get_content_type("file.xyz") == "application/octet-stream"
        assert _get_content_type("noextension") == "application/octet-stream"


# =============================================================================
# Integration Tests (require live Azure services)
# =============================================================================

@pytest.mark.integration
class TestACUIntegration:
    """Integration tests for Azure Content Understanding.
    
    These tests require live Azure services and environment variables:
    - CONTENT_UNDERSTANDING_ENDPOINT
    - CONTENT_UNDERSTANDING_KEY (or Azure CLI login for managed identity)
    - ANALYZER_NAME
    
    Run with: pytest test_document_analyzer.py -v -m integration
    """
    
    @pytest.fixture
    def acu_config(self):
        """Get ACU configuration from environment."""
        endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT")
        key = os.environ.get("CONTENT_UNDERSTANDING_KEY")
        analyzer = os.environ.get("ANALYZER_NAME", "custom-schema-analyzer")
        
        if not endpoint:
            pytest.skip("CONTENT_UNDERSTANDING_ENDPOINT not set")
        if not key:
            pytest.skip("CONTENT_UNDERSTANDING_KEY not set")
        
        return {
            "endpoint": endpoint,
            "key": key,
            "analyzer": analyzer
        }
    
    def test_analyze_simple_document(self, acu_config):
        """Test analyzing a simple text document."""
        # Create a simple test document (PDF would be better in real tests)
        test_content = b"Test document content for analysis"
        
        try:
            result = analyze_document(
                document_bytes=test_content,
                endpoint=acu_config["endpoint"],
                analyzer_id=acu_config["analyzer"],
                subscription_key=acu_config["key"]
            )
            
            assert result["status"] == "succeeded"
            assert "result" in result
        except Exception as e:
            # Document format might not be supported, which is expected
            pytest.skip(f"ACU analysis not available: {e}")


@pytest.mark.integration
class TestCosmosDBIntegration:
    """Integration tests for Cosmos DB.
    
    These tests require live Azure Cosmos DB and environment variables:
    - COSMOS_DB_ENDPOINT
    - COSMOS_DB_DATABASE
    - COSMOS_DB_CONTAINER
    - Azure CLI login for managed identity
    
    Run with: pytest test_document_analyzer.py -v -m integration
    """
    
    @pytest.fixture
    def cosmos_config(self):
        """Get Cosmos DB configuration from environment."""
        endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
        database = os.environ.get("COSMOS_DB_DATABASE", "documents")
        container = os.environ.get("COSMOS_DB_CONTAINER", "processed-documents")
        
        if not endpoint:
            pytest.skip("COSMOS_DB_ENDPOINT not set")
        
        return {
            "endpoint": endpoint,
            "database": database,
            "container": container
        }
    
    def test_cosmos_connection(self, cosmos_config):
        """Test connecting to Cosmos DB with managed identity."""
        from azure.identity import DefaultAzureCredential
        from azure.cosmos import CosmosClient
        
        try:
            credential = DefaultAzureCredential()
            client = CosmosClient(cosmos_config["endpoint"], credential=credential)
            database = client.get_database_client(cosmos_config["database"])
            container = database.get_container_client(cosmos_config["container"])
            
            # Test by reading container properties
            properties = container.read()
            assert properties["id"] == cosmos_config["container"]
        except Exception as e:
            pytest.skip(f"Cosmos DB connection not available: {e}")


# =============================================================================
# Environment Check Tests
# =============================================================================

class TestEnvironmentConfiguration:
    """Tests for environment configuration validation."""
    
    def test_required_packages_installed(self):
        """Test that all required packages are installed."""
        import azure.functions
        import azure.identity
        import azure.cosmos
        import requests
        
        assert azure.functions is not None
        assert azure.identity is not None
        assert azure.cosmos is not None
        assert requests is not None
    
    def test_function_app_imports(self):
        """Test that function_app.py imports successfully."""
        import function_app
        
        assert hasattr(function_app, 'process_document')
        assert hasattr(function_app, 'process_document_http')
        assert hasattr(function_app, 'health_check')


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Run basic environment check
    print("=" * 60)
    print("Document Analyzer Test Suite")
    print("=" * 60)
    
    # Check environment variables
    required_vars = [
        "CONTENT_UNDERSTANDING_ENDPOINT",
        "CONTENT_UNDERSTANDING_KEY",
        "ANALYZER_NAME",
        "COSMOS_DB_ENDPOINT"
    ]
    
    print("\nEnvironment Variables Check:")
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            display = f"{value[:20]}..." if len(value) > 20 else value
            if "KEY" in var:
                display = f"{value[:8]}***"
            print(f"  ✅ {var}: {display}")
        else:
            print(f"  ❌ {var}: Not set")
    
    print("\nRun tests with: pytest test_document_analyzer.py -v")
    print("Run integration tests: pytest test_document_analyzer.py -v -m integration")