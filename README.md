# Event Driven Document Processing Accelerator
Welcome to the Event Driven Document Processing solution accelerator. It's a lightweight template to extract information from documents. This solution accelerator uses Azure Azure AI Content Understanding and Azure Functions.

Azure AI Content Understanding is a powerful solution for extracting structured insights from unstructured data. Designed for developers building intelligent automation workflows, it streamlines the process of analyzing content by unifying layout analysis, semantic extraction, and schema-driven interpretation into a single, cohesive interface. This eliminates the need for complex manual parsing or custom ML pipelines, enabling scalable, low-latency insight extraction across diverse formats. Whether you're working with documents, videos or audio files, Azure AI Content Understanding delivers high-quality results that integrate seamlessly into your business logic. 
</br>
[Learn more about Azure AI Content Understanding](https://actual-url-here.com).

## Features

This accelerator helps simplify the extraction of information from documents.

The solution includes:

- An end-to-end pipeline triggered by the upload of documents to a blob storage
- Flexible configuration to customize schemas
- Easy integration with other architectures (just upload the document to the blob storage). Output binding can be easily swapped for your desired source

> You can also try Azure AI Content Understanding via the Azure AI Foundry UI for quick experimentation before deploying this template to your own Azure subscription.

### Architecture diagram

![Architecture Diagram](diagram.png)

## Getting Started

### Prerequisites and Costs
To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups and resources**. Follow the steps in [Azure Account Set Up](./docs/AzureAccountSetUp.md).

Check the [Azure Products by Region](https://azure.microsoft.com/explore/global-infrastructure/products-by-region/table) page and select a **region** where the following services are available: Azure AI Foundry Speech, Azure Communication Services, Azure Container Apps, and Container Registry.

Here are some example regions where the services are available: `westus`, `swedencentral`, `australiaeast`.
Pricing varies per region and usage, so it isn't possible to predict exact costs for your usage. The majority of the Azure resources used in this infrastructure are on usage-based pricing tiers.

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator) to calculate the cost of this solution in your subscription.

| Product | Description | Cost |
|---|---|---|
| [Azure AI Content Understanding ](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live/) | Low-latency and high-quality speech to speech interactions | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/) |
| [Azure Functions](https://learn.microsoft.com/azure/communication-services/overview) | Server-based intelligent call workflows | [Pricing](https://azure.microsoft.com/pricing/details/communication-services/) |
| [Azure Cosmos DB](https://learn.microsoft.com/azure/container-apps/) | Hosts the web application frontend | [Pricing](https://azure.microsoft.com/pricing/details/container-apps/) |
| [Azure Blob Storage](https://learn.microsoft.com/azure/container-registry/) | Stores container images for deployment | [Pricing](https://azure.microsoft.com/pricing/details/container-registry/) |


Here are some developers tools to set up as prerequisites:
- [Azure CLI](https://learn.microsoft.com/cli/azure/what-is-azure-cli): `az`
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview): `azd`
- [Python](https://www.python.org/about/gettingstarted/): `python`
- [UV](https://docs.astral.sh/uv/getting-started/installation/): `uv`
- Optionally [Docker](https://www.docker.com/get-started/): `docker`


### Deployment Options
Pick from the options below to see step-by-step instructions for: GitHub Codespaces, VS Code Dev Containers, Local Environments, and Bicep deployments.


## Resources