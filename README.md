# Event Driven Document Processing Accelerator

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?repo=NicoGrassetto/Event-driven-document-processing-accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/NicoGrassetto/Event-driven-document-processing-accelerator)
|---|---|

Welcome to the Event Driven Document Processing solution accelerator. It's a lightweight template to extract information from documents. This solution accelerator uses Azure AI Content Understanding, Azure Functions (Flex Consumption), and Azure Cosmos DB.

Azure AI Content Understanding is a powerful solution for extracting structured insights from unstructured data. Designed for developers building intelligent automation workflows, it streamlines the process of analyzing content by unifying layout analysis, semantic extraction, and schema-driven interpretation into a single, cohesive interface. This eliminates the need for complex manual parsing or custom ML pipelines, enabling scalable, low-latency insight extraction across diverse formats. Whether you're working with documents, videos or audio files, Azure AI Content Understanding delivers high-quality results that integrate seamlessly into your business logic.

[Learn more about Azure AI Content Understanding](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/).


<br/>

<div align="center">
  
[**Features**](#features) \| [**Getting Started**](#getting-started) \| [**Usage**](#usage) \| [**Customization**](#customization) \| [**Resources**](#resources)

</div>

## Features

This accelerator helps simplify the extraction of information from documents.

The solution includes:

- **Blob-triggered processing**: Automatically processes documents uploaded to Azure Blob Storage
- **Managed Identity authentication**: Secure, keyless authentication to all Azure services
- **Flex Consumption plan**: Cost-effective, auto-scaling Azure Functions
- **Cosmos DB output**: Extracted data stored in a serverless Cosmos DB database
- **Custom schema support**: Flexible field extraction based on your JSON schema
- **HTTP debug endpoint**: Manual trigger for testing document processing

> You can also try Azure AI Content Understanding via the Azure AI Foundry UI for quick experimentation before deploying this template to your own Azure subscription.

### Architecture diagram

![Architecture Diagram](diagram.png)

### How It Works

1. **Upload**: Documents are uploaded to the `documents` container in Azure Blob Storage
2. **Trigger**: The blob trigger automatically detects new uploads and starts processing
3. **Analyze**: Azure AI Content Understanding extracts fields defined in your schema
4. **Store**: Extracted data is saved to Cosmos DB with metadata (document ID, filename, timestamp)

## Getting Started

### Prerequisites and Costs
To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups and resources**.

Check the [Azure Products by Region](https://azure.microsoft.com/explore/global-infrastructure/products-by-region/table) page and select a **region** where the following services are available: Azure AI Foundry Speech, Azure Communication Services, Azure Container Apps, and Container Registry.

Here are some example regions where the services are available: `westus`, `swedencentral`, `australiaeast`.
Pricing varies per region and usage, so it isn't possible to predict exact costs for your usage. The majority of the Azure resources used in this infrastructure are on usage-based pricing tiers.

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator) to calculate the cost of this solution in your subscription.

| Product | Description | Cost |
|---|---|---|
| [Azure AI Content Understanding ](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/) | Extracts insights from unstructured content like documents, images, and videos using AI models | [Pricing](https://azure.microsoft.com/en-us/pricing/details/content-understanding/?msockid=2b189776556f650e3a1882ef5427649e) |
| [Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/) | Serverless compute service that runs event-driven code without managing infrastructure | [Pricing](https://azure.microsoft.com/en-us/pricing/details/functions/?msockid=2b189776556f650e3a1882ef5427649e) |
| [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/) | Globally distributed NoSQL database for scalable, low-latency data storage and access | [Pricing](https://azure.microsoft.com/en-us/pricing/details/cosmos-db/autoscale-provisioned/?msockid=2b189776556f650e3a1882ef5427649e) |
| [Azure Blob Storage](https://docs.azure.cn/en-us/storage/blobs/) | Object storage solution for unstructured data like documents, images, and backups | [Pricing](https://azure.microsoft.com/en-us/pricing/details/storage/blobs/?msockid=2b189776556f650e3a1882ef5427649e) |


Here are some developer tools to set up as prerequisites:

- [Azure CLI](https://learn.microsoft.com/cli/azure/what-is-azure-cli): `az`
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview): `azd`
- [Python 3.11+](https://www.python.org/about/gettingstarted/): `python`
- [PowerShell](https://learn.microsoft.com/powershell/scripting/install/installing-powershell) (for Windows) or Bash (for Linux/macOS)

> **Note**: Due to Azure Policy restrictions in some subscriptions, key-based authentication may be disabled on storage accounts. See the [Usage](#usage) section for how to upload files using Azure AD authentication.


### Deployment Options
Pick from the options below to see step-by-step instructions for: GitHub Codespaces, VS Code Dev Containers, Local Environments, and Bicep deployments.

<details>
  <summary><b>Deploy in GitHub Codespaces</b></summary>
  
#### GitHub Codespaces

You can run this solution using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the solution accelerator (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?repo=NicoGrassetto/Event-driven-document-processing-accelerator)

2. Accept the default values on the create Codespaces page.
3. Open a terminal window if it is not already open.
4. Follow the instructions in the helper script to populate deployment variables.
5. Continue with the [deploying steps](#deploying).

</details>

<details>
  <summary><b>Deploy in VS Code Dev Containers </b></summary>

#### VS Code Dev Containers

You can run this solution in VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it, if not already installed)
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/NicoGrassetto/Event-driven-document-processing-accelerator)


3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Follow the instructions in the helper script to populate deployment variables.
5. Continue with the [deploying steps](#deploying).

</details>

<details>
  <summary><b>Deploy in your local environment</b></summary>

 #### Local environment

If you're not using one of the above options for opening the project, then you'll need to:

1. Make sure the following tools are installed:

    * `bash`
    * [Azure Developer CLI (azd)](https://aka.ms/install-azd)

2. Download the project code:

    ```shell
    azd init -t NicoGrassetto/Event-driven-document-processing-accelerator
    ```
    **Note:** the above command should be run in a new folder of your choosing. You do not need to run `git clone` to download the project source code. `azd init` handles this for you.

3. Open the project folder in your terminal or editor.
4. Continue with the [deploying steps](#deploying).

</details>
 
### Deploying

Once you've opened the project in [Codespaces](#github-codespaces) or in [Dev Containers](#vs-code-dev-containers) or [locally](#local-environment), you can deploy it to Azure following the following steps. 

To change the `azd` parameters from the default values, follow the steps [here](./docs/customizing_azd_parameters.md). 

1. Login to Azure:

    ```shell
    azd auth login
    ```

2. Provision and deploy all the resources:

    ```shell
    azd up
    ```
    It will prompt you to provide an `azd` environment name (like "my-solution"), select a subscription from your Azure account, and select a location (like "eastus"). Then it will provision the resources in your account and deploy the latest code. If you get an error with deployment, changing the location can help, as there may be availability constraints for some of the resources.

3. When `azd` has finished deploying, you'll see the resource group alongside resources in the Azure Portal.

4. When you've made any changes to the code, you can just run:

    ```shell
    azd deploy
    ```

> [!NOTE]
> The `azd up` command will provision infrastructure, deploy the function app, and create a custom Content Understanding analyzer based on `schemas/schema.json`.

## Usage

### Uploading Documents

Due to Azure Policy restrictions in many subscriptions, storage account key-based authentication is disabled. Use Azure AD authentication instead:

```powershell
# Upload a document using Azure CLI with your identity
az storage blob upload \
  --account-name <STORAGE_ACCOUNT_NAME> \
  --container-name documents \
  --file "path/to/your/document.pdf" \
  --name "document.pdf" \
  --auth-mode login \
  --overwrite
```

> **First-time setup**: You need the "Storage Blob Data Contributor" role on the storage account. The deployment automatically assigns this role to the Function App's managed identity, but you may need to assign it to your user account manually:
> ```powershell
> az role assignment create \
>   --assignee <YOUR_USER_ID_OR_EMAIL> \
>   --role "Storage Blob Data Contributor" \
>   --scope "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>/providers/Microsoft.Storage/storageAccounts/<STORAGE_NAME>"
> ```

### Testing with HTTP Endpoint

For debugging, you can manually trigger document processing via the HTTP endpoint:

```powershell
# Get the function key
$funcKey = az functionapp keys list --name <FUNCTION_APP_NAME> --resource-group <RG_NAME> --query "functionKeys.default" -o tsv

# Trigger processing
Invoke-RestMethod -Uri "https://<FUNCTION_APP_NAME>.azurewebsites.net/api/process?code=$funcKey" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"blob_name": "document.pdf", "container_name": "documents"}'
```

### Viewing Results

Processed documents are stored in Cosmos DB:
- **Database**: `documents`
- **Container**: `processed-documents`
- **Partition Key**: `/documentId`

Each document includes:
- `documentId`: Unique identifier
- `fileName`: Original blob name
- `processedAt`: Timestamp
- `extractedFields`: Fields extracted based on your schema

## Customization

### Modifying the Extraction Schema

Edit `schemas/schema.json` to define the fields you want to extract:

```json
{
  "version": "1.0",
  "description": "Your custom schema description",
  "fields": [
    {
      "fieldKey": "FieldName",
      "fieldType": "string",
      "description": "Description of what to extract"
    },
    {
      "fieldKey": "Amount",
      "fieldType": "number",
      "description": "A numeric value to extract"
    },
    {
      "fieldKey": "Date",
      "fieldType": "date",
      "description": "A date value to extract"
    }
  ]
}
```

**Supported field types**: `string`, `number`, `date`, `boolean`, `array`, `object`

After modifying the schema, recreate the analyzer:

```powershell
# Windows
.\scripts\create-analyzer.ps1 -ResourceGroup <RG_NAME> -DeploymentName <DEPLOYMENT_NAME>

# Linux/macOS
./scripts/create-analyzer.sh
```

### Default Schema Fields

The default schema extracts purchase receipt information:
- `FirstName` - Customer's first name
- `LastName` - Customer's last name
- `DateOfPurchase` - Purchase date
- `Amount` - Total amount
- `Location` - Purchase location
- `StoreName` - Store/business name

## Resources

- [📖 Docs: Azure AI Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- [📖 Samples: Python code samples](https://github.com/Azure-Samples/azure-ai-content-understanding-python)
- [📖 Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [📖 Azure Cosmos DB Python SDK](https://learn.microsoft.com/azure/cosmos-db/nosql/sdk-python)
