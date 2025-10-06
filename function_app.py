import azure.functions as func
import logging
import json
from src.utils import analyze_document, get_credentials_from_env

app = func.FunctionApp()

@app.blob_trigger(
    arg_name="myblob", 
    path="documents/{name}",
    connection="AzureWebJobsStorage"
)
@app.cosmos_db_output(
    arg_name="outputDocument",
    database_name="DocumentAnalysisDB",
    container_name="AnalysisResults",
    connection="CosmosDBConnection",
    create_if_not_exists=True
)
def process_document_blob(myblob: func.InputStream, outputDocument: func.Out[func.Document]):
    """Process documents uploaded to Azure Blob Storage using blob upload triggers.
    
    This Azure Function is triggered automatically when a document is uploaded to the
    'documents' container in Azure Blob Storage. It performs comprehensive document 
    analysis using Azure AI Content Understanding service and stores the structured 
    results in Azure Cosmos DB for downstream processing and retrieval.
    
    The function implements a complete document processing pipeline:
        1. Validates required configuration from environment variables
        2. Reads the uploaded document content from blob storage
        3. Submits document to Azure AI Content Understanding for analysis
        4. Processes and structures the analysis results
        5. Stores results in Cosmos DB with metadata and status tracking
        6. Handles errors gracefully with detailed logging and error storage
    
    Blob Trigger Integration:
        - Trigger: Blob upload events in the 'documents' container
        - Source: Azure Blob Storage polling mechanism
        - Benefits: Simple setup, no additional configuration needed
    
    Input Binding:
        myblob (func.InputStream): Stream containing the uploaded document.
            - name (str): Full path/name of the blob (e.g., "invoices/invoice_001.pdf")
            - length (int): Size of the document in bytes
            - uri (str): Full URI to the blob in Azure Storage
            - read() -> bytes: Method to read the document content
    
    Output Binding:
        outputDocument (func.Out[func.Document]): Cosmos DB output binding.
            - database: "DocumentAnalysisDB"
            - container: "AnalysisResults"
            - Automatically creates database/container if they don't exist
    
    Environment Variables Required:
        - CONTENT_UNDERSTANDING_ENDPOINT: Azure AI service endpoint URL
        - CONTENT_UNDERSTANDING_KEY: Azure AI service subscription key
        - ANALYZER_NAME: Name of the custom analyzer to use
        - AzureWebJobsStorage: Connection string for blob storage (automatic)
        - CosmosDBConnection: Connection string for Cosmos DB output
    
    Cosmos DB Output Document Structure:
        Success case:
        {
            "id": str,  # Sanitized blob name (slashes and dots replaced with underscores)
            "blobName": str,  # Original blob name/path
            "blobUri": str,  # Full URI to the source blob
            "blobSize": int,  # Document size in bytes
            "analysisResults": {
                "metadata": {...},
                "extracted_fields": {...},
                "confidence_scores": {...},
                "summary": {...}
            },
            "processingStatus": "completed",
            "timestamp": str  # UTC timestamp of analysis
        }
        
        Error case:
        {
            "id": str,  # Sanitized blob name with "_error" suffix
            "blobName": str,
            "blobUri": str,
            "processingStatus": "failed",
            "errorType": str,  # "configuration_error" or "processing_error"
            "errorMessage": str  # Detailed error description
        }
    
    Raises:
        ValueError: If required environment variables are not configured.
            Exception is logged and an error document is written to Cosmos DB.
        Exception: If document analysis or processing fails.
            Exception is logged and an error document is written to Cosmos DB.
            The function re-raises the exception for Azure Functions runtime handling.
    
    Example Event Flow:
        1. User uploads 'invoice.pdf' to 'documents' container
        2. Blob trigger detects the new file via polling
        3. Function is triggered with blob input stream
        4. Document is analyzed: extracts invoice number, date, amount, etc.
        5. Results stored in Cosmos DB with id "documents_invoice_pdf"
        6. Function completes, logs summary statistics
    
    Example Log Output (Success):
        INFO: Processing blob: documents/invoice_001.pdf
        INFO: Blob Size: 245632 bytes
        INFO: Starting analysis for: documents/invoice_001.pdf
        INFO: Analysis complete for documents/invoice_001.pdf
        INFO: Extraction Quality: excellent
        INFO: Total Fields Extracted: 12
        INFO: Average Confidence: 0.93
        INFO: Successfully stored analysis results in Cosmos DB
    
    Example Log Output (Configuration Error):
        ERROR: Configuration error: Missing required configuration. Check environment variables.
    
    Example Log Output (Processing Error):
        ERROR: Error processing document invoice.pdf: Analysis failed: Invalid document format
    
    Note:
        The function uses a standard blob trigger that polls the storage account
        for new blobs. While simpler to set up than Event Grid, it may have a slight
        delay (typically a few seconds) in detecting new blobs depending on the
        polling interval.
        
        Error documents are written to the same Cosmos DB container to maintain a
        complete audit trail. Filter by processingStatus field to identify failures.
        
        The function sanitizes blob names to create valid Cosmos DB document IDs by
        replacing slashes and dots with underscores. Original blob names are preserved
        in the 'blobName' field.
    
    Performance Considerations:
        - Processing time varies based on document size and complexity (typically 2-30 seconds)
        - Azure Functions consumption plan provides automatic scaling
        - Cosmos DB throughput should be provisioned based on expected document volume
        - Consider implementing parallel processing for batch scenarios
    
    See Also:
        analyze_document: Core document analysis function in utils module
        get_credentials_from_env: Retrieves configuration from environment
    """
    logging.info(f"Processing blob: {myblob.name}")
    logging.info(f"Blob Size: {myblob.length} bytes")
    logging.info(f"Blob URI: {myblob.uri}")
    
    try:
        # Get credentials from environment
        config = get_credentials_from_env()
        
        # Validate configuration
        if not all([config["CONTENT_UNDERSTANDING_ENDPOINT"], 
                   config["CONTENT_UNDERSTANDING_KEY"], 
                   config["ANALYZER_NAME"]]):
            raise ValueError("Missing required configuration. Check environment variables.")
        
        # Read document content
        document_content = myblob.read()
        
        # Analyze document using utils module
        blob_name = myblob.name or "unknown"
        logging.info(f"Starting analysis for: {blob_name}")
        results = analyze_document(
            endpoint=config["CONTENT_UNDERSTANDING_ENDPOINT"],
            api_key=config["CONTENT_UNDERSTANDING_KEY"],
            analyzer_name=config["ANALYZER_NAME"],
            document_content=document_content,
            filename=blob_name
        )
        
        # Log analysis summary
        quality = results.get('summary', {}).get('extraction_quality', 'unknown')
        total_fields = results.get('summary', {}).get('total_fields_extracted', 0)
        avg_confidence = results.get('summary', {}).get('average_confidence', 0)
        
        logging.info(f"Analysis complete for {blob_name}")
        logging.info(f"Extraction Quality: {quality}")
        logging.info(f"Total Fields Extracted: {total_fields}")
        logging.info(f"Average Confidence: {avg_confidence:.2f}")
        
        # Prepare document for Cosmos DB
        doc_id = blob_name.replace("/", "_").replace(".", "_")
        cosmos_document = {
            "id": doc_id,  # Cosmos DB id
            "blobName": blob_name,
            "blobUri": myblob.uri,
            "blobSize": myblob.length,
            "analysisResults": results,
            "processingStatus": "completed",
            "timestamp": results.get("metadata", {}).get("analysis_timestamp")
        }
        
        # Write to Cosmos DB
        outputDocument.set(func.Document.from_dict(cosmos_document))
        
        logging.info(f"Successfully stored analysis results for {blob_name} in Cosmos DB")
        
    except ValueError as ve:
        logging.error(f"Configuration error: {str(ve)}")
        # Store error in Cosmos DB
        blob_name = myblob.name or "unknown"
        error_id = blob_name.replace("/", "_").replace(".", "_") + "_error"
        error_document = {
            "id": error_id,
            "blobName": blob_name,
            "blobUri": myblob.uri,
            "processingStatus": "failed",
            "errorType": "configuration_error",
            "errorMessage": str(ve)
        }
        outputDocument.set(func.Document.from_dict(error_document))
        raise
        
    except Exception as e:
        blob_name = myblob.name or "unknown"
        logging.error(f"Error processing document {blob_name}: {str(e)}")
        # Store error in Cosmos DB
        error_id = blob_name.replace("/", "_").replace(".", "_") + "_error"
        error_document = {
            "id": error_id,
            "blobName": blob_name,
            "blobUri": myblob.uri,
            "processingStatus": "failed",
            "errorType": "processing_error",
            "errorMessage": str(e)
        }
        outputDocument.set(func.Document.from_dict(error_document))
        raise


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Provide a health check endpoint for monitoring and availability verification.
    
    This HTTP-triggered Azure Function serves as a health check endpoint that can be
    used by monitoring systems, load balancers, Application Insights availability tests,
    or other health monitoring tools to verify that the Function App is running and
    responsive. The endpoint is publicly accessible without authentication.
    
    The health check:
        - Returns a 200 OK status when the function app is operational
        - Provides basic service metadata (service name, status, timestamp)
        - Uses anonymous authentication for easy access by monitoring tools
        - Can be called repeatedly without side effects (idempotent)
        - Responds quickly with minimal processing overhead
    
    HTTP Trigger Configuration:
        - Route: /api/health
        - Method: GET only
        - Authentication: Anonymous (no API key required)
        - CORS: Inherits from function app CORS settings
    
    Args:
        req (func.HttpRequest): The HTTP request object. This endpoint does not
            require any query parameters or request body. All parameters are ignored.
    
    Returns:
        func.HttpResponse: JSON response with the following structure:
            Status Code: 200 (OK)
            Content-Type: application/json
            Body:
            {
                "status": "healthy",
                "service": "document-processing-function",
                "timestamp": "2025-10-06T14:32:15.123456+00:00"
            }
            
            Fields:
                - status (str): Always "healthy" if function responds
                - service (str): Identifier for this function app
                - timestamp (str): UTC timestamp in ISO 8601 format with timezone
    
    Example Requests:
        >>> # Using curl
        >>> curl https://my-function-app.azurewebsites.net/api/health
        {
          "status": "healthy",
          "service": "document-processing-function",
          "timestamp": "2025-10-06T14:32:15.123456+00:00"
        }
        
        >>> # Using Python requests
        >>> import requests
        >>> response = requests.get("https://my-function-app.azurewebsites.net/api/health")
        >>> print(response.status_code)
        200
        >>> print(response.json()["status"])
        healthy
        
        >>> # Using Azure CLI for testing
        >>> az rest --method get --url "https://my-function-app.azurewebsites.net/api/health"
    
    Use Cases:
        1. Application Insights Availability Tests:
           Configure URL ping test pointing to /api/health endpoint
        
        2. Azure Front Door Health Probes:
           Set health probe path to /api/health for backend health monitoring
        
        3. Load Balancer Health Checks:
           Configure load balancer to probe /api/health for traffic distribution
        
        4. CI/CD Pipeline Validation:
           Call health endpoint after deployment to verify successful deployment
        
        5. Monitoring Dashboard:
           Periodically poll health endpoint to display service status
        
        6. Dependency Monitoring:
           Check health before submitting documents for processing
    
    Example Integration with Azure Monitor:
        ```python
        # Application Insights availability test configuration
        {
            "name": "Document Processing Health Check",
            "url": "https://my-function-app.azurewebsites.net/api/health",
            "frequency": 300,  # seconds
            "timeout": 30,
            "locations": ["us-west-2", "us-east-1", "europe-west"]
        }
        ```
    
    Example Monitoring Script:
        ```python
        import requests
        import time
        
        def monitor_health(url, interval=60):
            while True:
                try:
                    response = requests.get(f"{url}/api/health", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✓ Service healthy at {data['timestamp']}")
                    else:
                        print(f"✗ Unexpected status: {response.status_code}")
                except Exception as e:
                    print(f"✗ Health check failed: {e}")
                time.sleep(interval)
        
        monitor_health("https://my-function-app.azurewebsites.net")
        ```
    
    Note:
        This is a basic health check that only verifies the function app is running.
        It does NOT check:
            - Azure AI Content Understanding service availability
            - Cosmos DB connectivity
            - Blob Storage accessibility
            - Environment variable configuration
        
        For deeper health checks that validate dependencies, consider creating
        a separate /api/health/deep endpoint that tests connectivity to all
        dependent services (though this may be slower and use resources).
        
        The anonymous authentication level means this endpoint is publicly accessible.
        It does not expose any sensitive information, but be aware it can be called
        by anyone with the URL.
    
    Performance:
        - Response time: <100ms (minimal processing)
        - No external dependencies or I/O operations
        - Safe to call frequently (every 5-60 seconds)
        - Does not count against rate limits or quotas
    
    Security:
        - No sensitive data is exposed in the response
        - Cannot be used to trigger processing or modify state
        - Does not reveal internal architecture details
        - Safe for public internet access
    
    See Also:
        process_document_blob: Main document processing function
        Azure Monitor: https://docs.microsoft.com/azure/azure-monitor/
        Application Insights: https://docs.microsoft.com/azure/azure-monitor/app/
    """
    logging.info('Health check requested')
    
    from datetime import datetime, timezone
    health_status = {
        "status": "healthy",
        "service": "document-processing-function",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return func.HttpResponse(
        json.dumps(health_status, indent=2),
        status_code=200,
        mimetype="application/json"
    )
