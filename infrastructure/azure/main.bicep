targetScope = 'resourceGroup'

@description('Azure region used for the CaseMesh API resources.')
param location string = resourceGroup().location

@description('Azure region used for the Static Web App.')
param staticWebAppLocation string = 'eastasia'

@description('Container Apps environment name.')
param environmentName string = 'casemesh-env-dev'

@description('CaseMesh API Container App name.')
param containerAppName string = 'casemesh-api-dev'

@description('CaseMesh frontend Static Web App name.')
param staticWebAppName string = 'casemesh-web-dev'

@description('CaseMesh API container image.')
param containerImage string = 'ghcr.io/mohamadktich/casemesh-api:phase31c1-cors'

@description('Port exposed by the CaseMesh API container.')
@minValue(1)
@maxValue(65535)
param targetPort int = 8000

@description('Minimum number of running API replicas.')
@minValue(0)
param minReplicas int = 0

@description('Maximum number of running API replicas.')
@minValue(1)
param maxReplicas int = 1

@description('Browser origins allowed to call the CaseMesh REST API.')
param corsAllowedOrigins array = [
  'http://localhost:3000'
  'https://zealous-pebble-08744c900.5.azurestaticapps.net'
]

@description('Microsoft Entra tenant ID.')
param entraTenantId string

@description('Microsoft Entra application/client ID protecting the CaseMesh API.')
param entraApiClientId string

@description('Embedding provider.')
param embeddingProvider string = 'huggingface'

@description('Embedding model.')
param embeddingModel string = 'BAAI/bge-base-en-v1.5'

@description('Embedding vector dimension.')
param embeddingDimension string = '768'

@description('Generation provider.')
param generationProvider string = 'huggingface'

@description('Generation model.')
param generationModel string = 'Qwen/Qwen3-4B-Instruct-2507:cheapest'

@description('Global controlled action execution switch.')
param actionExecutionEnabled string = 'false'

@description('Controlled action execution mode.')
param actionExecutionMode string = 'dry_run'

@description('Comma-separated live execution allowlist.')
param actionExecutionLiveAllowlist string = 'update_case_status'

@description('Public hostname used by the remote MCP transport.')
param mcpPublicHostname string

@description('Whether investigation workflows use MCP.')
param investigationUseMcp string = 'true'

@description('MCP URL used by the investigation workflow inside the API container.')
param mcpClientUrl string = 'http://127.0.0.1:8000/mcp/'

@description('MCP client timeout in seconds.')
param mcpClientTimeoutSeconds string = '120'

@secure()
@description('Existing CaseMesh PostgreSQL database URL secret value.')
param databaseUrlSecret string

@secure()
@description('Existing Hugging Face token secret value.')
param hfTokenSecret string

@secure()
@description('Existing MCP authentication token secret value.')
param mcpAuthTokenSecret string

@secure()
@description('Existing Microsoft provider authentication secret value.')
param microsoftProviderAuthenticationSecret string


var commonTags = {
  project: 'CaseMesh-AI'
  environment: 'dev'
  managedBy: 'Bicep'
  phase: '31'
}


module environment './modules/environment.bicep' = {
  name: 'casemesh-environment'
  params: {
    environmentName: environmentName
    location: location
    tags: commonTags
  }
}


module api './modules/container-app.bicep' = {
  name: 'casemesh-container-app'
  params: {
    containerAppName: containerAppName
    location: location
    environmentId: environment.outputs.environmentId

    containerImage: containerImage
    targetPort: targetPort

    minReplicas: minReplicas
    maxReplicas: maxReplicas

    corsAllowedOrigins: corsAllowedOrigins

    entraTenantId: entraTenantId
    entraApiClientId: entraApiClientId

    embeddingProvider: embeddingProvider
    embeddingModel: embeddingModel
    embeddingDimension: embeddingDimension

    generationProvider: generationProvider
    generationModel: generationModel

    actionExecutionEnabled: actionExecutionEnabled
    actionExecutionMode: actionExecutionMode
    actionExecutionLiveAllowlist: actionExecutionLiveAllowlist

    mcpPublicHostname: mcpPublicHostname
    investigationUseMcp: investigationUseMcp
    mcpClientUrl: mcpClientUrl
    mcpClientTimeoutSeconds: mcpClientTimeoutSeconds

    databaseUrlSecret: databaseUrlSecret
    hfTokenSecret: hfTokenSecret
    mcpAuthTokenSecret: mcpAuthTokenSecret
    microsoftProviderAuthenticationSecret: microsoftProviderAuthenticationSecret

    tags: commonTags
  }
}


module web './modules/static-web-app.bicep' = {
  name: 'casemesh-static-web-app'
  params: {
    staticWebAppName: staticWebAppName
    location: staticWebAppLocation
    tags: commonTags
  }
}


output environmentName string = environment.outputs.environmentName

output containerAppName string = api.outputs.containerAppName

output containerAppUrl string = 'https://${api.outputs.fqdn}'

output staticWebAppName string = web.outputs.staticWebAppName

output staticWebAppHostname string = web.outputs.defaultHostname

output staticWebAppUrl string = 'https://${web.outputs.defaultHostname}'