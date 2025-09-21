#!/bin/bash

# Deployment script for Azure AI Content Understanding with analyzer creation

set -e  # Exit on any error

# Variables
DEPLOYMENT_NAME="data-extraction-deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Data Extraction service deployment...${NC}"
echo ""

# Deploy Bicep template
echo -e "${BLUE}Building Bicep template to ARM JSON...${NC}"
az bicep build --file infra/main.bicep --outfile infra/main.json

echo -e "${BLUE}Deploying infrastructure...${NC}"
echo -e "${BLUE}Note: You will be prompted for resource group and location if not specified${NC}"
az deployment group create \
  --template-file infra/main.bicep \
  --name $DEPLOYMENT_NAME

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Infrastructure deployment completed successfully!${NC}"
    
    # Call the analyzer creation script
    echo -e "${BLUE}Creating analyzer...${NC}"
    if [ -f "./create-analyzer.sh" ]; then
        ./create-analyzer.sh
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Full deployment and setup completed!${NC}"
        else
            echo -e "${RED}✗ Analyzer creation failed, but infrastructure is deployed.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ create-analyzer.sh script not found!${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Infrastructure deployment failed!${NC}"
    exit 1
fi
