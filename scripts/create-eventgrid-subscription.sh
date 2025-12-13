#!/bin/bash

# Script to create Event Grid subscription after function deployment
# Uses AzureFunction endpoint type which doesn't require webhook validation

set -e

echo "Creating Event Grid subscription for document processing..."

# Configuration
MAX_RETRIES=3
RETRY_DELAY=10
INITIAL_DELAY=90

# Progress indicator function
wait_with_progress() {
    local total=$1
    local interval=10
    echo -n "Waiting ${total}s for function to warm up"
    for ((i=0; i<total; i+=interval)); do
        sleep $interval
        echo -n "."
    done
    echo " done"
}

# Get deployment outputs
OUTPUTS=$(azd env get-values)

# Parse environment variables - use the actual Bicep output names
FUNCTION_APP_NAME=$(echo "$OUTPUTS" | grep "^functionAppName=" | cut -d'=' -f2 | tr -d '"' || echo "")
STORAGE_ACCOUNT_NAME=$(echo "$OUTPUTS" | grep "^storageAccountName=" | cut -d'=' -f2 | tr -d '"' || echo "")
RESOURCE_GROUP=$(echo "$OUTPUTS" | grep "^resourceGroupName=" | cut -d'=' -f2 | tr -d '"' || echo "")
SUBSCRIPTION_ID=$(echo "$OUTPUTS" | grep "^subscriptionId=" | cut -d'=' -f2 | tr -d '"' || echo "")

# Fallback lookups if variables are empty
if [ -z "$FUNCTION_APP_NAME" ] || [ "$FUNCTION_APP_NAME" == "null" ]; then
    FUNCTION_APP_NAME=$(az functionapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'func-')].name" -o tsv | head -n1)
fi

if [ -z "$STORAGE_ACCOUNT_NAME" ] || [ "$STORAGE_ACCOUNT_NAME" == "null" ]; then
    STORAGE_ACCOUNT_NAME=$(az storage account list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'storage')].name" -o tsv | head -n1)
fi

if [ -z "$SUBSCRIPTION_ID" ]; then
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

if [ -z "$RESOURCE_GROUP" ]; then
    RESOURCE_GROUP=$(azd env get-values | grep "AZURE_ENV_NAME" | cut -d'=' -f2 | tr -d '"')
    RESOURCE_GROUP="rg-${RESOURCE_GROUP}"
fi

# Get Event Grid topic name
EVENTGRID_TOPIC_NAME=$(az eventgrid system-topic list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'evgt-')].name" -o tsv | head -n1)

if [ -z "$FUNCTION_APP_NAME" ] || [ -z "$STORAGE_ACCOUNT_NAME" ] || [ -z "$EVENTGRID_TOPIC_NAME" ]; then
    echo "Error: Could not determine required resource names."
    echo "Function App: $FUNCTION_APP_NAME"
    echo "Storage Account: $STORAGE_ACCOUNT_NAME"
    echo "Event Grid Topic: $EVENTGRID_TOPIC_NAME"
    echo "Resource Group: $RESOURCE_GROUP"
    exit 1
fi

echo "Function App: $FUNCTION_APP_NAME"
echo "Storage Account: $STORAGE_ACCOUNT_NAME"
echo "Event Grid Topic: $EVENTGRID_TOPIC_NAME"
echo "Resource Group: $RESOURCE_GROUP"

# Build the function resource ID for AzureFunction endpoint type
FUNCTION_RESOURCE_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${FUNCTION_APP_NAME}/functions/process_document_eventgrid"

echo "Function Resource ID: $FUNCTION_RESOURCE_ID"

# Function to create/update Event Grid subscription with retries
create_subscription() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        echo "Attempt $attempt of $MAX_RETRIES..."
        
        # Check if subscription already exists
        EXISTING_SUB=$(az eventgrid system-topic event-subscription list \
            --resource-group "$RESOURCE_GROUP" \
            --system-topic-name "$EVENTGRID_TOPIC_NAME" \
            --query "[?name=='documents-created-subscription'].name" -o tsv 2>/dev/null || echo "")

        if [ -n "$EXISTING_SUB" ]; then
            echo "Event Grid subscription already exists. Updating..."
            if az eventgrid system-topic event-subscription update \
                --name documents-created-subscription \
                --resource-group "$RESOURCE_GROUP" \
                --system-topic-name "$EVENTGRID_TOPIC_NAME" \
                --endpoint-type azurefunction \
                --endpoint "$FUNCTION_RESOURCE_ID" \
                --included-event-types Microsoft.Storage.BlobCreated \
                --subject-begins-with "/blobServices/default/containers/documents/blobs/" \
                --max-delivery-attempts 30 \
                --event-ttl 1440 2>&1; then
                return 0
            fi
        else
            echo "Creating new Event Grid subscription..."
            if az eventgrid system-topic event-subscription create \
                --name documents-created-subscription \
                --resource-group "$RESOURCE_GROUP" \
                --system-topic-name "$EVENTGRID_TOPIC_NAME" \
                --endpoint-type azurefunction \
                --endpoint "$FUNCTION_RESOURCE_ID" \
                --included-event-types Microsoft.Storage.BlobCreated \
                --subject-begins-with "/blobServices/default/containers/documents/blobs/" \
                --max-delivery-attempts 30 \
                --event-ttl 1440 2>&1; then
                return 0
            fi
        fi
        
        echo "  Waiting for function to be ready... (${RETRY_DELAY}s)"
        sleep $RETRY_DELAY
        attempt=$((attempt + 1))
    done
    
    echo "Error: Failed to create Event Grid subscription after $MAX_RETRIES attempts."
    return 1
}

# Wait for function to be ready before attempting subscription creation
wait_with_progress $INITIAL_DELAY

# Run the creation with retries
create_subscription

echo "✓ Event Grid subscription created/updated successfully!"
