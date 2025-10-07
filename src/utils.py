import time
import requests


def analyze_document(
    document_bytes: bytes,
    endpoint: str,
    subscription_key: str,
    analyzer_id: str,
    api_version: str = "2025-05-01-preview"
) -> dict:
    """Analyzes a document using Azure Content Understanding service.
    
    Args:
        document_bytes: The document content as bytes.
        endpoint: The Azure Content Understanding endpoint URL.
        subscription_key: The Azure subscription key for authentication.
        analyzer_id: The ID of the analyzer to use.
        api_version: The API version to use. Defaults to "2025-05-01-preview".
    
    Returns:
        A dictionary containing the analysis results including extracted text,
        tables, figures, and other document elements.
    
    Raises:
        requests.HTTPError: If the API request fails.
        RuntimeError: If the analysis operation fails.
    """
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
        "Content-Type": "application/octet-stream"
    }
    
    url = f"{endpoint.rstrip('/')}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_version}&stringEncoding=utf16"
    response = requests.post(url, headers=headers, data=document_bytes)
    response.raise_for_status()
    
    operation_location = response.headers.get("operation-location")
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    
    while True:
        response = requests.get(operation_location, headers=headers)
        response.raise_for_status()
        result = response.json()
        status = result.get("status", "").lower()
        
        if status == "succeeded":
            return result
        elif status == "failed":
            raise RuntimeError("Analysis failed")
        
        time.sleep(1)
