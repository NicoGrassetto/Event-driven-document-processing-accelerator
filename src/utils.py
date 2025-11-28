import time
import logging
from typing import Optional, Union

import requests
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


def _get_auth_headers(
    credential: Optional[DefaultAzureCredential] = None,
    subscription_key: Optional[str] = None
) -> dict:
    """Get authentication headers using managed identity or subscription key.
    
    Args:
        credential: Azure credential for managed identity authentication.
        subscription_key: Subscription key for key-based authentication.
    
    Returns:
        Dictionary containing authentication headers.
    
    Raises:
        ValueError: If neither credential nor subscription_key is provided.
    """
    if credential is not None:
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}
    elif subscription_key is not None:
        return {"Ocp-Apim-Subscription-Key": subscription_key}
    else:
        raise ValueError("Either credential or subscription_key must be provided")


def analyze_document(
    document_bytes: bytes,
    endpoint: str,
    analyzer_id: str,
    credential: Optional[DefaultAzureCredential] = None,
    subscription_key: Optional[str] = None,
    api_version: str = "2025-05-01-preview"
) -> dict:
    """Analyzes a document using Azure Content Understanding service.
    
    Supports both managed identity (DefaultAzureCredential) and subscription key
    authentication. For production, use managed identity. For local development,
    subscription key can be used as a fallback.
    
    Args:
        document_bytes: The document content as bytes.
        endpoint: The Azure Content Understanding endpoint URL.
        analyzer_id: The ID of the analyzer to use.
        credential: Azure credential for managed identity authentication.
            If provided, takes precedence over subscription_key.
        subscription_key: The Azure subscription key for authentication.
            Used as fallback when credential is not provided.
        api_version: The API version to use. Defaults to "2025-05-01-preview".
    
    Returns:
        A dictionary containing the analysis results including extracted text,
        tables, figures, and other document elements.
    
    Raises:
        requests.HTTPError: If the API request fails.
        RuntimeError: If the analysis operation fails.
        ValueError: If neither credential nor subscription_key is provided.
    """
    auth_headers = _get_auth_headers(credential, subscription_key)
    headers = {
        **auth_headers,
        "Content-Type": "application/octet-stream"
    }
    
    url = f"{endpoint.rstrip('/')}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_version}&stringEncoding=utf16"
    
    logger.info(f"Starting document analysis with analyzer: {analyzer_id}")
    response = requests.post(url, headers=headers, data=document_bytes)
    response.raise_for_status()
    
    operation_location = response.headers.get("operation-location")
    poll_headers = _get_auth_headers(credential, subscription_key)
    
    while True:
        response = requests.get(operation_location, headers=poll_headers)
        response.raise_for_status()
        result = response.json()
        status = result.get("status", "").lower()
        
        if status == "succeeded":
            logger.info("Document analysis completed successfully")
            return result
        elif status == "failed":
            error_msg = result.get("error", {}).get("message", "Unknown error")
            logger.error(f"Document analysis failed: {error_msg}")
            raise RuntimeError(f"Analysis failed: {error_msg}")
        
        logger.debug(f"Analysis status: {status}, polling...")
        time.sleep(1)


def extract_fields_from_result(result: dict) -> dict:
    """Extract field values from ACU analysis result.
    
    Args:
        result: The raw analysis result from analyze_document.
    
    Returns:
        A dictionary containing extracted field names and their values.
    """
    fields = {}
    
    # Navigate to the extracted fields in the result
    analyze_result = result.get("result", {})
    contents = analyze_result.get("contents", [])
    
    for content in contents:
        content_fields = content.get("fields", {})
        for field_name, field_data in content_fields.items():
            if isinstance(field_data, dict):
                # Extract the value based on field type
                value = field_data.get("valueString") or \
                        field_data.get("valueNumber") or \
                        field_data.get("valueDate") or \
                        field_data.get("value")
                fields[field_name] = value
            else:
                fields[field_name] = field_data
    
    return fields
