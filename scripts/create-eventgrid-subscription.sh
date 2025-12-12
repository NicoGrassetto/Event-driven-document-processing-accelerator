#!/bin/bash

# Script to create Event Grid subscription after function deployment

set -e

echo "Creating Event Grid subscription for document processing..."

# Get deployment outputs
OUTPUTS=$(azd env get-values)

# Parse environment variables
FUNCTION_APP_NAME=$(echo "$OUTPUTS" | grep "SERVICE_API_NAME" | cut -d'=' -f2 | tr -d '"' || echo "")
STORAGE_ACCOUNT_NAME=$(echo "$OUTPUTS" | grep "AZURE_STORAGE_ACCOUNT_NAME" | cut -d'=' -f2 | tr -d '"' || echo "")
RESOURCE_GROUP=$(echo "$OUTPUTS" | grep "AZURE_RESOURCE_GROUP_NAME" | cut -d'=' -f2 | tr -d '"' || echo "")
SUBSCRIPTION_ID=$(echo "$OUTPUTS" | grep "AZURE_SUBSCRIPTION_ID" | cut -d'=' -f2 | tr -d '"' || echo "")

# If variables are still empty, try alternative names or get from azd outputs
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

# Get function app keys for webhook endpoint
echo "Getting function app system key..."
SYSTEM_KEY=$(az functionapp keys list --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "systemKeys.eventgrid_extension" -o tsv 2>/dev/null || echo "")

# If eventgrid_extension key doesn't exist, use the default key
if [ -z "$SYSTEM_KEY" ]; then
    echo "Event Grid extension key not found, using master key..."
    MASTER_KEY=$(az functionapp keys list --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "masterKey" -o tsv)
    WEBHOOK_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net/runtime/webhooks/eventgrid?functionName=process_document_eventgrid&code=${MASTER_KEY}"
else
    WEBHOOK_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net/runtime/webhooks/eventgrid?functionName=process_document_eventgrid&code=${SYSTEM_KEY}"
fi

echo "Webhook URL configured"

# Check if subscription already exists
EXISTING_SUB=$(az eventgrid system-topic event-subscription list \
    --resource-group "$RESOURCE_GROUP" \
    --system-topic-name "$EVENTGRID_TOPIC_NAME" \
    --query "[?name=='documents-created-subscription'].name" -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING_SUB" ]; then
    echo "Event Grid subscription already exists. Updating..."
    az eventgrid system-topic event-subscription update \
        --name documents-created-subscription \
        --resource-group "$RESOURCE_GROUP" \
        --system-topic-name "$EVENTGRID_TOPIC_NAME" \
        --endpoint-type webhook \
        --endpoint "$WEBHOOK_URL" \
        --included-event-types Microsoft.Storage.BlobCreated \
        --subject-begins-with "/blobServices/default/containers/documents/blobs/" \
        --max-delivery-attempts 30 \
        --event-ttl 1440
else
    echo "Creating new Event Grid subscription..."
    az eventgrid system-topic event-subscription create \
        --name documents-created-subscription \
        --resource-group "$RESOURCE_GROUP" \
        --system-topic-name "$EVENTGRID_TOPIC_NAME" \
        --endpoint-type webhook \
        --endpoint "$WEBHOOK_URL" \
        --included-event-types Microsoft.Storage.BlobCreated \
        --subject-begins-with "/blobServices/default/containers/documents/blobs/" \
        --max-delivery-attempts 30 \
        --event-ttl 1440
fi

echo "✓ Event Grid subscription created/updated successfully!"
echo "Documents uploaded to /documents in the storage account will now trigger the function."
