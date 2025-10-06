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
    """Get credentials from environment variables (Azure Function App Settings)"""
    return {
        "CONTENT_UNDERSTANDING_ENDPOINT": os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", ""),
        "CONTENT_UNDERSTANDING_KEY": os.environ.get("CONTENT_UNDERSTANDING_KEY", ""),
        "ANALYZER_NAME": os.environ.get("ANALYZER_NAME", "")
    }


# Helper Functions

def get_content_type(file_path: str) -> str:
    """Determine content type based on file extension"""
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
    """Extract the appropriate value from field data"""
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
    """Assess the overall quality of extraction"""
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
    """Submit document to the analyzer"""
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
    """Poll the operation location for results"""
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
    """Process results from custom schema analyzer"""
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
    """Process the analysis results into a structured format"""
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
    """
    Analyze a document using the configured analyzer
    
    Args:
        endpoint: Azure AI Content Understanding endpoint
        api_key: API key for authentication
        analyzer_name: Name of the analyzer to use
        document_content: Binary content of the document
        filename: Name of the file (for content type detection and metadata)
        
    Returns:
        Dictionary containing analysis results
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
    """
    Analyze a document from a file path (convenience wrapper)
    
    Args:
        file_path: Path to the document file
        endpoint: Azure AI Content Understanding endpoint (optional, reads from env if not provided)
        api_key: API key for authentication (optional, reads from env if not provided)
        analyzer_name: Name of the analyzer to use (optional, reads from env if not provided)
        
    Returns:
        Dictionary containing analysis results
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
