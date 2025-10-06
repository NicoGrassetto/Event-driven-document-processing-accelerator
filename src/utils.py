#!/usr/bin/env python3
"""
Azure AI Content Understanding Document Analyzer

This module provides a function to analyze documents using Azure AI Content Understanding service.
"""

import os
import time
import requests
from typing import Dict, Any, Optional


def analyze_document_bytes(
    document_content: bytes,
    content_type: str,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    analyzer_name: Optional[str] = None,
    max_retries: int = 60,
    retry_interval: int = 2
) -> Dict[str, Any]:
    """Analyze document bytes using Azure AI Content Understanding and return raw results.
    
    This function submits document bytes to Azure AI Content Understanding service,
    polls for completion, and returns the raw API response as a dictionary.
    
    Args:
        document_content (bytes): The binary content of the document to analyze.
        content_type (str): MIME type of the document (e.g., 'application/pdf', 'image/jpeg').
        endpoint (Optional[str]): Azure AI endpoint URL. If None, reads from 
            CONTENT_UNDERSTANDING_ENDPOINT environment variable.
        api_key (Optional[str]): API subscription key. If None, reads from 
            CONTENT_UNDERSTANDING_KEY environment variable.
        analyzer_name (Optional[str]): Name of the analyzer to use. If None, reads from 
            ANALYZER_NAME environment variable.
        max_retries (int): Maximum polling attempts. Defaults to 60.
        retry_interval (int): Seconds between polling attempts. Defaults to 2.
    
    Returns:
        Dict[str, Any]: Raw analysis results from Azure AI Content Understanding API.
    
    Raises:
        ValueError: If required credentials are missing.
        Exception: If API call fails or times out.
    
    Example:
        >>> with open('invoice.pdf', 'rb') as f:
        ...     content = f.read()
        >>> results = analyze_document_bytes(content, 'application/pdf')
        >>> print(results.keys())
    """
    # Get credentials from environment if not provided
    if not endpoint:
        endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    if not api_key:
        api_key = os.environ.get("CONTENT_UNDERSTANDING_KEY", "")
    if not analyzer_name:
        analyzer_name = os.environ.get("ANALYZER_NAME", "")
    
    # Validate credentials
    if not endpoint or not api_key or not analyzer_name:
        raise ValueError(
            "Missing required credentials. Provide endpoint, api_key, and analyzer_name "
            "as arguments or set CONTENT_UNDERSTANDING_ENDPOINT, CONTENT_UNDERSTANDING_KEY, "
            "and ANALYZER_NAME environment variables."
        )
    
    # Submit document for analysis
    url = f"{endpoint.rstrip('/')}/contentunderstanding/analyzers/{analyzer_name}:analyze"
    headers = {
        "Content-Type": content_type,
        "Ocp-Apim-Subscription-Key": api_key
    }
    params = {"api-version": "2025-05-01-preview"}
    
    response = requests.post(url, headers=headers, params=params, data=document_content)
    
    if response.status_code != 202:
        raise Exception(f"Failed to submit document: {response.status_code} - {response.text}")
    
    operation_location = response.headers.get("Operation-Location")
    if not operation_location:
        raise Exception("No operation location returned from API")
    
    # Poll for results
    poll_headers = {"Ocp-Apim-Subscription-Key": api_key}
    retries = 0
    
    while retries < max_retries:
        poll_response = requests.get(operation_location, headers=poll_headers)
        
        if poll_response.status_code != 200:
            raise Exception(
                f"Failed to get results: {poll_response.status_code} - {poll_response.text}"
            )
        
        result = poll_response.json()
        status = result.get("status", "unknown").lower()
        
        if status == "succeeded":
            # Return the raw result data
            if "result" in result:
                return result["result"]
            elif "analyzeResult" in result:
                return result["analyzeResult"]
            else:
                return result
        elif status == "failed":
            error_message = result.get("error", {}).get("message", "Unknown error")
            raise Exception(f"Analysis failed: {error_message}")
        elif status in ["notstarted", "running"]:
            time.sleep(retry_interval)
            retries += 1
        else:
            raise Exception(f"Unknown status: {status}")
    
    raise Exception(f"Analysis timed out after {max_retries * retry_interval} seconds")