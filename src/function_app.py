"""
Azure Function App for Event-Driven Document Processing

This function app processes documents uploaded to Azure Blob Storage,
extracts information using Azure Content Understanding (ACU),
and stores the results in Azure Cosmos DB.

Triggers:
    - Event Grid trigger: Automatically processes documents uploaded to 'documents' container via Azure Event Grid
    - HTTP trigger: Debug endpoint for manual document processing

Authentication:
    - Uses managed identity (DefaultAzureCredential) for all Azure services
    - Falls back to connection strings for local development
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient

from utils import analyze_document, extract_fields_from_result

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Function App
app = func.FunctionApp()

# Environment variables
COSMOS_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")
COSMOS_DATABASE = os.environ.get("COSMOS_DB_DATABASE", "documents")
COSMOS_CONTAINER = os.environ.get("COSMOS_DB_CONTAINER", "processed-documents")
ACU_ENDPOINT = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT")
ACU_KEY = os.environ.get("CONTENT_UNDERSTANDING_KEY")  # For local dev fallback
ANALYZER_ID = os.environ.get("ANALYZER_NAME", "custom-schema-analyzer")


def get_credential() -> Optional[DefaultAzureCredential]:
    """Get Azure credential for managed identity authentication.
    
    Returns None if running locally with connection strings.
    """
    # Check if we're running in Azure (managed identity available)
    if os.environ.get("IDENTITY_ENDPOINT"):
        return DefaultAzureCredential()
    # For local development, try to use DefaultAzureCredential which will
    # attempt various auth methods (Azure CLI, VS Code, etc.)
    try:
        credential = DefaultAzureCredential()
        # Test if credential works by getting a token
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception:
        logger.warning("Managed identity not available, falling back to keys")
        return None


def get_cosmos_client() -> CosmosClient:
    """Get Cosmos DB client using managed identity or connection string."""
    credential = get_credential()
    
    if credential and COSMOS_ENDPOINT:
        logger.info("Using managed identity for Cosmos DB")
        return CosmosClient(COSMOS_ENDPOINT, credential=credential)
    
    # Fallback to connection string for local development
    connection_string = os.environ.get("COSMOS_DB_CONNECTION_STRING")
    if connection_string:
        logger.info("Using connection string for Cosmos DB")
        return CosmosClient.from_connection_string(connection_string)
    
    raise ValueError(
        "Cosmos DB configuration missing. Set COSMOS_DB_ENDPOINT with managed identity "
        "or COSMOS_DB_CONNECTION_STRING for local development."
    )


def process_document_internal(
    document_bytes: bytes,
    document_name: str,
    content_type: str = "application/octet-stream"
) -> dict:
    """Process a document through ACU and store results in Cosmos DB.
    
    Args:
        document_bytes: The document content as bytes.
        document_name: The name of the document file.
        content_type: The MIME type of the document.
    
    Returns:
        Dictionary containing the processed document data and metadata.
    """
    document_id = str(uuid.uuid4())
    logger.info(f"Processing document: {document_name} (ID: {document_id})")
    
    # Get credential for ACU
    credential = get_credential()
    
    if not ACU_ENDPOINT:
        raise ValueError("CONTENT_UNDERSTANDING_ENDPOINT environment variable is required")
    
    # Analyze document using ACU
    logger.info(f"Analyzing document with ACU endpoint: {ACU_ENDPOINT}")
    
    try:
        result = analyze_document(
            document_bytes=document_bytes,
            endpoint=ACU_ENDPOINT,
            analyzer_id=ANALYZER_ID,
            credential=credential,
            subscription_key=ACU_KEY if not credential else None
        )
    except Exception as e:
        logger.error(f"ACU analysis failed: {str(e)}")
        raise
    
    # Extract fields from the result
    extracted_fields = extract_fields_from_result(result)
    logger.info(f"Extracted {len(extracted_fields)} fields from document")
    
    # Prepare document for Cosmos DB
    cosmos_document = {
        "id": document_id,
        "documentId": document_id,  # Partition key
        "fileName": document_name,
        "contentType": content_type,
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "extractedFields": extracted_fields,
        "rawResult": result,
        "status": "processed"
    }
    
    # Store in Cosmos DB
    try:
        cosmos_client = get_cosmos_client()
        database = cosmos_client.get_database_client(COSMOS_DATABASE)
        container = database.get_container_client(COSMOS_CONTAINER)
        
        container.upsert_item(cosmos_document)
        logger.info(f"Document stored in Cosmos DB: {document_id}")
    except Exception as e:
        logger.error(f"Failed to store document in Cosmos DB: {str(e)}")
        raise
    
    return cosmos_document


@app.event_grid_trigger(arg_name="event")
def process_document_eventgrid(event: func.EventGridEvent):
    """Process documents uploaded to the 'documents' blob container via Event Grid.
    
    This function is triggered automatically by Event Grid when a blob is created
    in the 'documents' container in the configured storage account.
    
    Args:
        event: The Event Grid event containing blob metadata.
    """
    logger.info(f"Event Grid trigger activated")
    logger.info(f"Event type: {event.event_type}")
    logger.info(f"Event subject: {event.subject}")
    
    try:
        # Extract blob information from Event Grid event
        event_data = event.get_json()
        blob_url = event_data.get('url')
        content_length = event_data.get('contentLength', 0)
        content_type = event_data.get('contentType', 'application/octet-stream')
        
        # Extract blob name from subject (format: /blobServices/default/containers/{container}/blobs/{blobname})
        subject_parts = event.subject.split('/blobs/')
        if len(subject_parts) < 2:
            logger.error(f"Invalid subject format: {event.subject}")
            return
        
        blob_path = subject_parts[1]
        file_name = blob_path.split("/")[-1]
        
        logger.info(f"Processing blob: {blob_path}")
        logger.info(f"Blob size: {content_length} bytes")
        logger.info(f"Content type: {content_type}")
        
        # Download blob content using managed identity
        credential = get_credential()
        storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
        
        if not storage_account_name:
            raise ValueError("STORAGE_ACCOUNT_NAME environment variable is required")
        
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account_name}.blob.core.windows.net",
            credential=credential
        )
        
        # Extract container and blob name from the path
        container_name = "documents"
        blob_name = blob_path
        
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        document_bytes = blob_client.download_blob().readall()
        
        logger.info(f"Downloaded {len(document_bytes)} bytes from blob storage")
        
        # Process the document
        result = process_document_internal(
            document_bytes=document_bytes,
            document_name=file_name,
            content_type=content_type
        )
        
        logger.info(f"Successfully processed document: {file_name}")
        logger.info(f"Document ID: {result['id']}")
        logger.info(f"Extracted fields: {list(result['extractedFields'].keys())}")
        
    except Exception as e:
        logger.error(f"Error processing Event Grid event: {str(e)}")
        logger.error(f"Event data: {event.get_json()}")
        raise


@app.route(route="process", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def process_document_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for manual document processing (debug/testing).
    
    This endpoint allows you to upload a document directly via HTTP POST
    for processing, useful for local development and testing.
    
    Request:
        - Method: POST
        - Body: Document file content (binary)
        - Headers:
            - Content-Type: The MIME type of the document
            - X-Document-Name: (Optional) The name of the document
    
    Returns:
        JSON response containing the processed document data.
    """
    logger.info("HTTP trigger activated for document processing")
    
    try:
        # Get document content from request body
        document_bytes = req.get_body()
        
        if not document_bytes:
            return func.HttpResponse(
                json.dumps({"error": "No document content provided"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Get document name from header or generate one
        document_name = req.headers.get("X-Document-Name", f"document_{uuid.uuid4().hex[:8]}")
        content_type = req.headers.get("Content-Type", "application/octet-stream")
        
        logger.info(f"Processing document via HTTP: {document_name}")
        logger.info(f"Content-Type: {content_type}, Size: {len(document_bytes)} bytes")
        
        # Process the document
        result = process_document_internal(
            document_bytes=document_bytes,
            document_name=document_name,
            content_type=content_type
        )
        
        # Return success response with extracted data
        response_data = {
            "success": True,
            "documentId": result["id"],
            "fileName": result["fileName"],
            "processedAt": result["processedAt"],
            "extractedFields": result["extractedFields"]
        }
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Configuration error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Processing failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint.
    
    Returns the status of the function app and its dependencies.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "cosmosEndpoint": bool(COSMOS_ENDPOINT),
            "acuEndpoint": bool(ACU_ENDPOINT),
            "analyzerConfigured": bool(ANALYZER_ID)
        }
    }
    
    return func.HttpResponse(
        json.dumps(health_status, indent=2),
        status_code=200,
        mimetype="application/json"
    )


def _get_content_type(file_name: str) -> str:
    """Get content type based on file extension.
    
    Args:
        file_name: The name of the file.
    
    Returns:
        The MIME type for the file.
    """
    extension = file_name.lower().split(".")[-1] if "." in file_name else ""
    
    content_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "bmp": "image/bmp",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    }
    
    return content_types.get(extension, "application/octet-stream")
