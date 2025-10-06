import azure.functions as func
import logging
import json
from src.utils import analyze_document, get_credentials_from_env

app = func.FunctionApp()

@app.blob_trigger(
    arg_name="myblob", 
    path="documents/{name}",
    connection="AzureWebJobsStorage",
    source=func.BlobSource.EVENT_GRID
)
@app.cosmos_db_output(
    arg_name="outputDocument",
    database_name="DocumentAnalysisDB",
    container_name="AnalysisResults",
    connection="CosmosDBConnection",
    create_if_not_exists=True
)
def process_document_blob(myblob: func.InputStream, outputDocument: func.Out[func.Document]):
    """
    Triggered when a document is uploaded to the 'documents' container via Event Grid.
    Analyzes the document using Azure AI Content Understanding and stores results in Cosmos DB.
    
    Input Binding: Blob Storage (Event Grid trigger)
    Output Binding: Cosmos DB
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
    """Health check endpoint for monitoring"""
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
