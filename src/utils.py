#!/usr/bin/env python3
"""
Azure AI Content Understanding Document Analyzer

This module provides functions to analyze documents using Azure AI Content Understanding service.
Designed to be used within Azure Functions for event-driven document processing.
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path


# Configuration Functions

def get_credentials_from_env() -> Dict[str, str]:
    """Retrieve Azure AI Content Understanding service credentials from environment variables.
    
    This function reads configuration values from the application's environment variables,
    which are typically set in Azure Function App Settings. It provides a centralized
    way to access service credentials without hardcoding sensitive information.
    
    The function looks for three specific environment variables:
        - CONTENT_UNDERSTANDING_ENDPOINT: The full URL of the Azure AI service endpoint
        - CONTENT_UNDERSTANDING_KEY: The subscription key for API authentication
        - ANALYZER_NAME: The name of the specific analyzer to use
    
    Returns:
        Dict[str, str]: A dictionary containing three keys:
            - "CONTENT_UNDERSTANDING_ENDPOINT" (str): Service endpoint URL, empty string if not set
            - "CONTENT_UNDERSTANDING_KEY" (str): API subscription key, empty string if not set
            - "ANALYZER_NAME" (str): Name of the analyzer, empty string if not set
    
    Example:
        >>> config = get_credentials_from_env()
        >>> print(config["CONTENT_UNDERSTANDING_ENDPOINT"])
        'https://my-service.cognitiveservices.azure.com/'
        >>> print(config["ANALYZER_NAME"])
        'invoice-analyzer'
    
    Note:
        This function does not validate whether the credentials are correctly set.
        Empty strings are returned for any missing environment variables.
        It is the caller's responsibility to verify that all required values are present.
    
    See Also:
        analyze_document_from_path: Uses this function to retrieve credentials automatically
    """
    return {
        "CONTENT_UNDERSTANDING_ENDPOINT": os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", ""),
        "CONTENT_UNDERSTANDING_KEY": os.environ.get("CONTENT_UNDERSTANDING_KEY", ""),
        "ANALYZER_NAME": os.environ.get("ANALYZER_NAME", "")
    }


# Helper Functions

def get_content_type(file_path: str) -> str:
    """Determine the MIME content type of a document based on its file extension.
    
    This function maps common document and image file extensions to their corresponding
    MIME types, which are required when submitting documents to the Azure AI Content
    Understanding API. The function performs case-insensitive extension matching.
    
    Supported file types:
        - PDF documents (.pdf)
        - JPEG images (.jpg, .jpeg)
        - PNG images (.png)
        - BMP images (.bmp)
        - TIFF images (.tiff, .tif)
        - GIF images (.gif)
    
    Args:
        file_path (str): The path or filename of the document. Can be a full path or
            just a filename. Only the extension is evaluated.
    
    Returns:
        str: The MIME content type string. Returns 'application/octet-stream' for
            unrecognized or unsupported file extensions.
    
    Example:
        >>> get_content_type("invoice.pdf")
        'application/pdf'
        >>> get_content_type("/path/to/document.jpg")
        'image/jpeg'
        >>> get_content_type("scan.TIFF")
        'image/tiff'
        >>> get_content_type("unknown.xyz")
        'application/octet-stream'
    
    Note:
        The function uses case-insensitive matching, so both 'FILE.PDF' and 'file.pdf'
        will return 'application/pdf'. Unrecognized extensions return a generic binary
        stream type rather than raising an error.
    """
    extension = Path(file_path).suffix.lower()
    
    content_type_map = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
        '.gif': 'image/gif'
    }
    
    return content_type_map.get(extension, 'application/octet-stream')


def extract_field_value(field_data: Dict[str, Any]) -> Any:
    """Recursively extract the actual value from Azure AI Content Understanding field data.
    
    Azure AI Content Understanding returns field data in various formats depending on the
    data type (strings, numbers, dates, arrays, objects). This function intelligently
    determines the field type and extracts the appropriate value, handling nested
    structures recursively.
    
    The function checks for value keys in the following priority order:
        1. "content" - Raw content field
        2. "valueString" - String value
        3. "valueNumber" - Numeric value
        4. "valueDate" - Date value
        5. "valueArray" - Array of values (can contain objects or primitives)
        6. "valueObject" - Nested object with multiple fields
    
    Args:
        field_data (Dict[str, Any]): A dictionary containing field information from the
            Azure AI response. Expected to contain at least one of the value keys
            mentioned above, along with optional metadata like confidence scores.
    
    Returns:
        Any: The extracted value, which can be:
            - str: For string or content fields
            - int/float: For numeric fields
            - str: For date fields (ISO format)
            - list: For array fields (may contain dicts, primitives, or mixed types)
            - dict: For object fields with nested key-value pairs
            - None: If no recognizable value key is found
    
    Example:
        >>> # Simple string field
        >>> field_data = {"valueString": "John Doe", "confidence": 0.95}
        >>> extract_field_value(field_data)
        'John Doe'
        
        >>> # Array of objects
        >>> field_data = {
        ...     "valueArray": [
        ...         {"valueObject": {"name": {"valueString": "Item1"}, "qty": {"valueNumber": 5}}},
        ...         {"valueObject": {"name": {"valueString": "Item2"}, "qty": {"valueNumber": 3}}}
        ...     ]
        ... }
        >>> extract_field_value(field_data)
        [{'name': 'Item1', 'qty': 5}, {'name': 'Item2', 'qty': 3}]
        
        >>> # Nested object
        >>> field_data = {
        ...     "valueObject": {
        ...         "street": {"valueString": "123 Main St"},
        ...         "zipCode": {"valueString": "12345"}
        ...     }
        ... }
        >>> extract_field_value(field_data)
        {'street': '123 Main St', 'zipCode': '12345'}
    
    Note:
        This function is called recursively to handle nested structures. It's designed
        to be robust and returns None for unrecognized field structures rather than
        raising exceptions.
    """
    # Try different value keys based on type
    if "content" in field_data:
        return field_data["content"]
    elif "valueString" in field_data:
        return field_data["valueString"]
    elif "valueNumber" in field_data:
        return field_data["valueNumber"]
    elif "valueDate" in field_data:
        return field_data["valueDate"]
    elif "valueArray" in field_data:
        # Handle array fields
        array_items = []
        for item in field_data["valueArray"]:
            if isinstance(item, dict) and "valueObject" in item:
                # Object array
                obj_data = {}
                for obj_field, obj_value in item["valueObject"].items():
                    obj_data[obj_field] = extract_field_value(obj_value)
                array_items.append(obj_data)
            else:
                array_items.append(extract_field_value(item))
        return array_items
    elif "valueObject" in field_data:
        # Handle object fields
        obj_data = {}
        for obj_field, obj_value in field_data["valueObject"].items():
            obj_data[obj_field] = extract_field_value(obj_value)
        return obj_data
    
    return None


def assess_extraction_quality(confidence_values: List[float]) -> str:
    """Assess the overall quality of document field extraction based on confidence scores.
    
    This function analyzes a collection of confidence scores to provide a qualitative
    assessment of extraction quality. It considers both the average confidence and the
    proportion of high-confidence extractions to determine an overall quality rating.
    
    The assessment uses two metrics:
        - Average confidence: Mean of all confidence scores
        - High confidence ratio: Proportion of scores above 0.8
    
    Quality ratings are determined as follows:
        - "excellent": avg > 0.9 AND >80% of fields have confidence > 0.8
        - "good": avg > 0.7 AND >60% of fields have confidence > 0.8
        - "fair": avg > 0.5
        - "poor": avg ≤ 0.5
        - "no_data": Empty confidence list
    
    Args:
        confidence_values (List[float]): A list of confidence scores, typically ranging
            from 0.0 to 1.0, where 1.0 represents maximum confidence. Each score
            represents the model's confidence in a particular field extraction.
    
    Returns:
        str: A qualitative assessment string, one of:
            - "excellent": Very high confidence across most fields
            - "good": High confidence with some medium-confidence fields
            - "fair": Mixed confidence levels, may require manual review
            - "poor": Low confidence, likely needs manual correction
            - "no_data": No confidence values provided (empty list)
    
    Example:
        >>> # Excellent quality - high confidence across all fields
        >>> assess_extraction_quality([0.95, 0.92, 0.88, 0.91])
        'excellent'
        
        >>> # Good quality - mostly high confidence
        >>> assess_extraction_quality([0.85, 0.75, 0.82, 0.78])
        'good'
        
        >>> # Fair quality - mixed confidence
        >>> assess_extraction_quality([0.65, 0.55, 0.72, 0.48])
        'fair'
        
        >>> # Poor quality - low confidence
        >>> assess_extraction_quality([0.35, 0.42, 0.38, 0.45])
        'poor'
        
        >>> # No data
        >>> assess_extraction_quality([])
        'no_data'
    
    Note:
        This assessment is subjective and based on empirical thresholds. Depending on
        your use case, you may want to adjust the thresholds or require manual review
        for "fair" or "poor" quality extractions.
    """
    if not confidence_values:
        return "no_data"
    
    avg_confidence = sum(confidence_values) / len(confidence_values)
    high_confidence_ratio = len([c for c in confidence_values if c > 0.8]) / len(confidence_values)
    
    if avg_confidence > 0.9 and high_confidence_ratio > 0.8:
        return "excellent"
    elif avg_confidence > 0.7 and high_confidence_ratio > 0.6:
        return "good"
    elif avg_confidence > 0.5:
        return "fair"
    else:
        return "poor"


# API Interaction Functions

def submit_document(endpoint: str, api_key: str, analyzer_name: str, 
                   document_content: bytes, content_type: str) -> str:
    """Submit a document to Azure AI Content Understanding for asynchronous analysis.
    
    This function initiates a document analysis operation by sending the document
    content to the Azure AI Content Understanding service. The service processes
    documents asynchronously, so this function returns an operation location URL
    that can be polled to retrieve results.
    
    The function constructs the appropriate API endpoint, sets required headers
    including authentication, and posts the document content. It expects a 202
    Accepted response with an Operation-Location header for tracking the operation.
    
    Args:
        endpoint (str): The Azure AI Content Understanding service endpoint URL.
            Should be in the format: 'https://<resource-name>.cognitiveservices.azure.com/'
            Trailing slashes are handled automatically.
        api_key (str): The subscription key for authenticating with the Azure service.
            This should be kept secure and not hardcoded in production code.
        analyzer_name (str): The name of the specific analyzer to use for processing.
            This should match an analyzer configured in your Azure AI service.
        document_content (bytes): The binary content of the document to analyze.
            Must be a valid document format (PDF, JPEG, PNG, etc.).
        content_type (str): The MIME type of the document (e.g., 'application/pdf',
            'image/jpeg'). Use get_content_type() to determine this automatically.
    
    Returns:
        str: The Operation-Location URL that can be used to poll for analysis results.
            This URL includes a unique operation ID and should be passed to
            poll_for_results() to retrieve the completed analysis.
    
    Raises:
        Exception: If the API returns a non-202 status code, indicating the document
            submission failed. The exception message includes the status code and
            detailed error response from the API.
        Exception: If the API response doesn't include an Operation-Location header,
            which is required to track the analysis operation.
    
    Example:
        >>> with open('invoice.pdf', 'rb') as f:
        ...     doc_content = f.read()
        >>> endpoint = "https://my-service.cognitiveservices.azure.com/"
        >>> api_key = "your-api-key-here"
        >>> analyzer = "invoice-analyzer"
        >>> content_type = "application/pdf"
        >>> operation_url = submit_document(endpoint, api_key, analyzer, doc_content, content_type)
        >>> print(operation_url)
        'https://my-service.cognitiveservices.azure.com/contentunderstanding/analyzers/invoice-analyzer/operations/12345-abcde'
    
    Note:
        This function uses the 2025-05-01-preview API version. The Azure AI Content
        Understanding service processes documents asynchronously, so immediate results
        are not available. Use poll_for_results() with the returned operation location
        to retrieve results once processing completes.
    
    See Also:
        poll_for_results: Poll the operation location for completed results
        get_content_type: Determine the appropriate content type from a filename
    """
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
    
    return operation_location


def poll_for_results(operation_location: str, api_key: str, max_retries: int = 60, 
                     retry_interval: int = 2) -> Dict[str, Any]:
    """Poll an Azure AI operation location until analysis completes or times out.
    
    This function implements a polling mechanism to retrieve results from an
    asynchronous document analysis operation. It repeatedly checks the operation
    status at regular intervals until the analysis succeeds, fails, or reaches
    the maximum retry limit.
    
    The function handles different operation states:
        - "succeeded": Analysis completed successfully, results are returned
        - "failed": Analysis failed, raises exception with error details
        - "notstarted" or "running": Analysis in progress, continues polling
        - Other states: Treated as errors
    
    Args:
        operation_location (str): The full URL to the operation status endpoint,
            obtained from the submit_document() function. This URL includes a
            unique operation ID that tracks the specific analysis job.
        api_key (str): The subscription key for authenticating with the Azure service.
            Must be the same key used to submit the document.
        max_retries (int, optional): Maximum number of polling attempts before
            timing out. Defaults to 60, which with the default retry_interval
            allows up to 2 minutes of processing time.
        retry_interval (int, optional): Number of seconds to wait between polling
            attempts. Defaults to 2 seconds. Increase for large documents that
            take longer to process.
    
    Returns:
        Dict[str, Any]: The analysis results dictionary containing extracted fields
            and metadata. The structure depends on the analyzer type but typically
            includes fields, confidence scores, and document structure information.
            The function extracts the actual results from various possible response
            structures ("result", "analyzeResult", or the full response).
    
    Raises:
        Exception: If the API returns a non-200 status code when checking operation
            status, indicating a communication or authentication error.
        Exception: If the analysis operation fails, with the error message from
            the Azure service included in the exception.
        Exception: If the operation status is unrecognized or invalid.
        Exception: If max_retries is reached without the operation completing
            (timeout), with details about the total time waited.
    
    Example:
        >>> # After submitting a document
        >>> operation_url = submit_document(...)
        >>> 
        >>> # Poll with default settings (up to 2 minutes)
        >>> results = poll_for_results(operation_url, api_key)
        >>> print(results.keys())
        dict_keys(['contents', 'pages', 'tables', ...])
        >>> 
        >>> # Poll with longer timeout for large documents
        >>> results = poll_for_results(operation_url, api_key, max_retries=120, retry_interval=5)
        >>> # This allows up to 10 minutes (120 * 5 seconds)
    
    Note:
        Processing time varies based on document size, complexity, and current service
        load. Simple single-page documents may process in seconds, while complex
        multi-page documents may take a minute or more. Adjust max_retries and
        retry_interval based on your expected document types.
        
        The function sleeps between retries, blocking execution. For async applications,
        consider implementing an async version using asyncio.sleep().
    
    See Also:
        submit_document: Submit a document and get the operation location
        analyze_document: High-level function that combines submission and polling
    """
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    
    retries = 0
    while retries < max_retries:
        response = requests.get(operation_location, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get results: {response.status_code} - {response.text}")
        
        result = response.json()
        status = result.get("status", "unknown").lower()
        
        if status == "succeeded":
            # Return the result data
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


# Processing Functions

def process_custom_extraction(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Process and structure results from an Azure AI custom schema analyzer.
    
    This function transforms raw API responses from Azure AI Content Understanding
    into a standardized, easy-to-use format. It handles multiple API response
    structures (current and legacy formats) and extracts field values and confidence
    scores, then calculates quality metrics.
    
    The function intelligently handles three different API response structures:
        1. Modern "contents" structure with "fields" (current API version)
        2. Modern "contents" structure with "extractedFields"
        3. Legacy "documents" structure (older API versions)
    
    For each extracted field, the function:
        - Recursively extracts the actual value (handling nested objects/arrays)
        - Captures the confidence score
        - Calculates summary statistics about extraction quality
    
    Args:
        analysis_result (Dict[str, Any]): The raw analysis result dictionary returned
            from the Azure AI Content Understanding API. Expected to contain either
            a "contents" array (current API) or "documents" array (legacy API).
    
    Returns:
        Dict[str, Any]: A processed dictionary with the following structure:
            {
                "extraction_type": "custom_schema",
                "extracted_fields": {
                    "field_name1": value1,
                    "field_name2": value2,
                    ...
                },
                "confidence_scores": {
                    "field_name1": 0.95,
                    "field_name2": 0.87,
                    ...
                },
                "summary": {
                    "total_fields_extracted": int,
                    "fields_with_high_confidence": int,  # confidence > 0.8
                    "fields_with_medium_confidence": int,  # 0.5 <= confidence <= 0.8
                    "fields_with_low_confidence": int,  # confidence < 0.5
                    "average_confidence": float,
                    "extraction_quality": str  # "excellent", "good", "fair", "poor", or "no_data"
                }
            }
    
    Example:
        >>> # Simple extraction with a few fields
        >>> api_response = {
        ...     "contents": [{
        ...         "fields": {
        ...             "invoice_number": {"valueString": "INV-12345", "confidence": 0.95},
        ...             "total_amount": {"valueNumber": 1299.99, "confidence": 0.92}
        ...         }
        ...     }]
        ... }
        >>> result = process_custom_extraction(api_response)
        >>> print(result["extracted_fields"])
        {'invoice_number': 'INV-12345', 'total_amount': 1299.99}
        >>> print(result["summary"]["extraction_quality"])
        'excellent'
        
        >>> # Extraction with no fields found
        >>> empty_response = {"contents": [{"fields": {}}]}
        >>> result = process_custom_extraction(empty_response)
        >>> print(result["summary"]["extraction_quality"])
        'no_data'
    
    Note:
        The function is designed to be robust and will return a valid structure
        even if no fields are extracted (summary will indicate "no_data" quality).
        Field values can be of any type (strings, numbers, dates, arrays, objects)
        and are extracted recursively using extract_field_value().
        
        Confidence scores range from 0.0 to 1.0, where 1.0 represents maximum
        confidence in the extracted value.
    
    See Also:
        extract_field_value: Recursively extracts values from field data
        assess_extraction_quality: Determines overall quality rating
        process_results: Higher-level function that calls this processor
    """
    processed = {
        "extraction_type": "custom_schema",
        "extracted_fields": {},
        "confidence_scores": {},
        "summary": {}
    }
    
    # Handle the new API structure
    if "contents" in analysis_result:
        contents = analysis_result["contents"]
        
        if contents and len(contents) > 0:
            content = contents[0]  # Process first content item
            
            # Check for fields structure (most common)
            if "fields" in content:
                fields_data = content["fields"] 
                for field_name, field_info in fields_data.items():
                    if isinstance(field_info, dict):
                        field_value = extract_field_value(field_info)
                        field_confidence = field_info.get("confidence", 0)
                        
                        processed["extracted_fields"][field_name] = field_value
                        processed["confidence_scores"][field_name] = field_confidence
            
            # Alternative: extractedFields structure
            elif "extractedFields" in content:
                fields_data = content["extractedFields"]
                
                for field_name, field_info in fields_data.items():
                    if isinstance(field_info, dict):
                        field_value = field_info.get("value", "")
                        field_confidence = field_info.get("confidence", 0)
                        
                        processed["extracted_fields"][field_name] = field_value
                        processed["confidence_scores"][field_name] = field_confidence
    
    # Fallback: check if documents exist (older API structure)
    elif "documents" in analysis_result:
        documents = analysis_result.get("documents", [])
        
        if documents:
            document = documents[0]
            fields = document.get("fields", {})
            
            for field_name, field_data in fields.items():
                if isinstance(field_data, dict):
                    field_value = extract_field_value(field_data)
                    field_confidence = field_data.get("confidence", 0)
                    
                    processed["extracted_fields"][field_name] = field_value
                    processed["confidence_scores"][field_name] = field_confidence
    
    # Calculate summary statistics
    confidence_values = list(processed["confidence_scores"].values())
    if confidence_values:
        processed["summary"] = {
            "total_fields_extracted": len(processed["extracted_fields"]),
            "fields_with_high_confidence": len([c for c in confidence_values if c > 0.8]),
            "fields_with_medium_confidence": len([c for c in confidence_values if 0.5 <= c <= 0.8]),
            "fields_with_low_confidence": len([c for c in confidence_values if c < 0.5]),
            "average_confidence": sum(confidence_values) / len(confidence_values),
            "extraction_quality": assess_extraction_quality(confidence_values)
        }
    else:
        processed["summary"] = {
            "total_fields_extracted": 0,
            "fields_with_high_confidence": 0,
            "fields_with_medium_confidence": 0,
            "fields_with_low_confidence": 0,
            "average_confidence": 0,
            "extraction_quality": "no_data"
        }
    
    return processed


def process_results(analysis_result: Dict[str, Any], filename: str, 
                   analyzer_name: str) -> Dict[str, Any]:
    """Process raw Azure AI analysis results into a complete, structured output format.
    
    This function serves as the main orchestrator for result processing, combining
    metadata about the analysis operation with the processed extraction results.
    It adds contextual information such as filename, analyzer details, and timestamp,
    then delegates to specialized processing functions based on analyzer type.
    
    The function creates a standardized output format that includes:
        - Metadata about the analysis (filename, analyzer, timestamp, API version)
        - Extracted field values and confidence scores
        - Summary statistics and quality assessment
    
    Args:
        analysis_result (Dict[str, Any]): The raw analysis result dictionary returned
            from poll_for_results(), containing the complete API response from Azure
            AI Content Understanding.
        filename (str): The name of the analyzed document file. Used for tracking
            and metadata purposes. Should include the file extension.
        analyzer_name (str): The name of the analyzer that was used to process the
            document. This helps identify which schema or model was applied.
    
    Returns:
        Dict[str, Any]: A comprehensive dictionary containing both metadata and
            processed results with the following structure:
            {
                "metadata": {
                    "filename": str,
                    "analyzer_name": str,
                    "analyzer_type": "extraction",
                    "analysis_timestamp": str,  # UTC timestamp
                    "api_version": "2025-05-01-preview"
                },
                "extraction_type": "custom_schema",
                "extracted_fields": {
                    "field1": value1,
                    "field2": value2,
                    ...
                },
                "confidence_scores": {
                    "field1": float,
                    "field2": float,
                    ...
                },
                "summary": {
                    "total_fields_extracted": int,
                    "fields_with_high_confidence": int,
                    "fields_with_medium_confidence": int,
                    "fields_with_low_confidence": int,
                    "average_confidence": float,
                    "extraction_quality": str
                }
            }
    
    Example:
        >>> # After receiving raw API results
        >>> raw_results = poll_for_results(operation_url, api_key)
        >>> processed = process_results(raw_results, "invoice_001.pdf", "invoice-analyzer")
        >>> 
        >>> # Access metadata
        >>> print(processed["metadata"]["filename"])
        'invoice_001.pdf'
        >>> print(processed["metadata"]["analysis_timestamp"])
        '2025-10-06 14:32:15 UTC'
        >>> 
        >>> # Access extracted data
        >>> print(processed["extracted_fields"]["invoice_number"])
        'INV-12345'
        >>> print(processed["summary"]["extraction_quality"])
        'excellent'
    
    Note:
        The timestamp is generated at the time this function is called, not when
        the analysis was actually performed by Azure AI. For precise timing, consider
        also tracking submission and completion times separately.
        
        Currently, this function always processes results as "custom_schema" extraction
        type. Future versions may support additional analyzer types (e.g., prebuilt
        models) with different processing logic.
    
    See Also:
        process_custom_extraction: Handles the extraction-specific processing
        analyze_document: High-level function that calls this after polling
    """
    processed = {
        "metadata": {
            "filename": filename,
            "analyzer_name": analyzer_name,
            "analyzer_type": "extraction",
            "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "api_version": "2025-05-01-preview"
        }
    }
    
    # Process custom schema results
    processed.update(process_custom_extraction(analysis_result))
    
    return processed


# Main Analysis Function

def analyze_document(endpoint: str, api_key: str, analyzer_name: str, 
                    document_content: bytes, filename: str) -> Dict[str, Any]:
    """Analyze a document using Azure AI Content Understanding with a custom analyzer.
    
    This is the primary function for document analysis. It orchestrates the complete
    analysis workflow: determining content type, submitting the document to Azure AI,
    polling for results, and processing the response into a structured format.
    
    The function handles the full lifecycle of document analysis:
        1. Determines MIME type from filename
        2. Submits document to Azure AI service (asynchronous operation)
        3. Polls operation status until completion
        4. Processes raw results into standardized format
        5. Returns complete analysis with metadata and quality metrics
    
    This function is designed to be called from Azure Functions or other serverless
    environments where you have document content in memory and need comprehensive
    analysis results.
    
    Args:
        endpoint (str): The Azure AI Content Understanding service endpoint URL.
            Format: 'https://<resource-name>.cognitiveservices.azure.com/'
            Must be a valid, reachable Azure service endpoint.
        api_key (str): The subscription key for authenticating with Azure AI service.
            This is the primary key or secondary key from your Azure resource.
            Keep this secure and use Azure Key Vault in production.
        analyzer_name (str): The name of the custom analyzer to use for processing.
            Must match an analyzer that has been created and trained in your
            Azure AI Content Understanding resource.
        document_content (bytes): The binary content of the document to analyze.
            Must be a complete, valid document in a supported format (PDF, JPEG,
            PNG, TIFF, BMP, GIF). Maximum size depends on Azure service limits.
        filename (str): The name of the document file, including extension.
            Used for content type detection and metadata tracking. Example: 'invoice.pdf'
    
    Returns:
        Dict[str, Any]: A comprehensive dictionary containing analysis results:
            {
                "metadata": {
                    "filename": str,
                    "analyzer_name": str,
                    "analyzer_type": "extraction",
                    "analysis_timestamp": str,
                    "api_version": str
                },
                "extraction_type": "custom_schema",
                "extracted_fields": Dict[str, Any],
                "confidence_scores": Dict[str, float],
                "summary": {
                    "total_fields_extracted": int,
                    "fields_with_high_confidence": int,
                    "fields_with_medium_confidence": int,
                    "fields_with_low_confidence": int,
                    "average_confidence": float,
                    "extraction_quality": str
                }
            }
    
    Raises:
        Exception: If document submission fails (invalid endpoint, auth issues, etc.)
        Exception: If the analysis operation fails during processing
        Exception: If polling times out (document too large or service unavailable)
        Exception: If the API returns unexpected response format
    
    Example:
        >>> # Analyze a document from memory (e.g., in Azure Function)
        >>> with open('invoice.pdf', 'rb') as f:
        ...     content = f.read()
        >>> 
        >>> endpoint = "https://my-doc-ai.cognitiveservices.azure.com/"
        >>> api_key = "your-subscription-key"
        >>> analyzer = "invoice-analyzer"
        >>> 
        >>> results = analyze_document(endpoint, api_key, analyzer, content, "invoice.pdf")
        >>> 
        >>> # Check extraction quality
        >>> print(f"Quality: {results['summary']['extraction_quality']}")
        Quality: excellent
        >>> 
        >>> # Access extracted fields
        >>> print(f"Invoice #: {results['extracted_fields']['invoice_number']}")
        Invoice #: INV-12345
        >>> 
        >>> # Review confidence scores
        >>> for field, score in results['confidence_scores'].items():
        ...     print(f"{field}: {score:.2%}")
        invoice_number: 95.00%
        total_amount: 92.00%
    
    Note:
        This function blocks while waiting for analysis to complete (up to 2 minutes
        by default). Processing time varies based on document complexity. For very
        large documents or batch processing, consider implementing asynchronous
        patterns or increasing timeout values in poll_for_results().
        
        The function automatically determines content type from the filename extension.
        Ensure the filename has the correct extension matching the actual document format.
    
    See Also:
        analyze_document_from_path: Convenience wrapper that reads from file path
        submit_document: Low-level function for document submission
        poll_for_results: Low-level function for result polling
        process_results: Result processing and formatting
    """
    # Determine content type
    content_type = get_content_type(filename)
    
    # Submit document for analysis
    operation_location = submit_document(endpoint, api_key, analyzer_name, 
                                        document_content, content_type)
    
    # Poll for results
    results = poll_for_results(operation_location, api_key)
    
    # Process and return results
    return process_results(results, filename, analyzer_name)


def analyze_document_from_path(file_path: str, endpoint: Optional[str] = None, 
                               api_key: Optional[str] = None, 
                               analyzer_name: Optional[str] = None) -> Dict[str, Any]:
    """Analyze a document from a file path with automatic credential management.
    
    This convenience function simplifies document analysis when working with files
    on the local filesystem. It automatically handles file reading, credential
    retrieval from environment variables (if not explicitly provided), and delegates
    to analyze_document() for the actual analysis.
    
    This function is ideal for:
        - Local testing and development
        - Batch processing of files
        - CLI tools and scripts
        - Any scenario where documents are stored as files rather than in memory
    
    The function provides flexible credential handling:
        - Explicitly provide all credentials (for testing or multi-environment setups)
        - Provide some credentials and read others from environment
        - Provide no credentials and read all from environment variables
    
    Args:
        file_path (str): Absolute or relative path to the document file to analyze.
            The file must exist and be readable. Supported formats: PDF, JPEG, PNG,
            TIFF, BMP, GIF. File extension is used for content type detection.
        endpoint (Optional[str], optional): Azure AI Content Understanding endpoint URL.
            If None, reads from CONTENT_UNDERSTANDING_ENDPOINT environment variable.
            Format: 'https://<resource-name>.cognitiveservices.azure.com/'
        api_key (Optional[str], optional): Subscription key for Azure AI service.
            If None, reads from CONTENT_UNDERSTANDING_KEY environment variable.
            Keep this secure; use environment variables in production.
        analyzer_name (Optional[str], optional): Name of the custom analyzer to use.
            If None, reads from ANALYZER_NAME environment variable.
            Must match an analyzer in your Azure resource.
    
    Returns:
        Dict[str, Any]: Complete analysis results in the same format as analyze_document():
            {
                "metadata": {...},
                "extraction_type": "custom_schema",
                "extracted_fields": {...},
                "confidence_scores": {...},
                "summary": {...}
            }
    
    Raises:
        FileNotFoundError: If the specified file_path does not exist.
        ValueError: If required credentials are missing (not provided as arguments
            and not found in environment variables).
        Exception: Any exception raised by analyze_document() during processing.
        OSError: If the file cannot be read due to permissions or I/O errors.
    
    Example:
        >>> # Using environment variables for credentials
        >>> os.environ['CONTENT_UNDERSTANDING_ENDPOINT'] = 'https://my-service.cognitiveservices.azure.com/'
        >>> os.environ['CONTENT_UNDERSTANDING_KEY'] = 'your-api-key'
        >>> os.environ['ANALYZER_NAME'] = 'invoice-analyzer'
        >>> 
        >>> results = analyze_document_from_path('documents/invoice_001.pdf')
        >>> print(f"Extracted {results['summary']['total_fields_extracted']} fields")
        Extracted 12 fields
        
        >>> # Providing credentials explicitly (useful for testing multiple analyzers)
        >>> results = analyze_document_from_path(
        ...     'receipts/receipt.jpg',
        ...     endpoint='https://test-service.cognitiveservices.azure.com/',
        ...     api_key='test-key',
        ...     analyzer_name='receipt-analyzer'
        ... )
        
        >>> # Mixed: some from env, some explicit
        >>> results = analyze_document_from_path(
        ...     'documents/contract.pdf',
        ...     analyzer_name='contract-analyzer'  # Others from env
        ... )
        
        >>> # Batch processing example
        >>> import glob
        >>> for pdf_file in glob.glob('documents/*.pdf'):
        ...     try:
        ...         results = analyze_document_from_path(pdf_file)
        ...         print(f"{pdf_file}: {results['summary']['extraction_quality']}")
        ...     except Exception as e:
        ...         print(f"{pdf_file}: Error - {e}")
    
    Note:
        The function reads the entire file into memory before sending to Azure AI.
        For very large files, ensure sufficient memory is available. Azure AI has
        file size limits that vary by service tier.
        
        When using environment variables, ensure they are set before calling this
        function. In production, use Azure Key Vault or similar secure storage
        for API keys rather than plain environment variables.
    
    See Also:
        analyze_document: Core analysis function (for in-memory content)
        get_credentials_from_env: Retrieves credentials from environment
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found: {file_path}")
    
    # Get credentials from environment if not provided
    if not endpoint or not api_key or not analyzer_name:
        config = get_credentials_from_env()
        endpoint = endpoint or config["CONTENT_UNDERSTANDING_ENDPOINT"]
        api_key = api_key or config["CONTENT_UNDERSTANDING_KEY"]
        analyzer_name = analyzer_name or config["ANALYZER_NAME"]
    
    # Validate credentials
    if not endpoint or not api_key or not analyzer_name:
        raise ValueError("Missing required credentials. Provide them as arguments or set environment variables.")
    
    # Read document content
    with open(file_path, 'rb') as file:
        document_content = file.read()
    
    filename = os.path.basename(file_path)
    
    return analyze_document(endpoint, api_key, analyzer_name, document_content, filename)
