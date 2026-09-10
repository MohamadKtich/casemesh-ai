using '../main.bicep'

param location = 'uaenorth'
param staticWebAppLocation = 'eastasia'

param environmentName = 'casemesh-env-dev'
param containerAppName = 'casemesh-api-dev'
param staticWebAppName = 'casemesh-web-dev'

param containerImage = 'ghcr.io/mohamadktich/casemesh-api:phase31c1-cors'
param targetPort = 8000

param minReplicas = 0
param maxReplicas = 1

param corsAllowedOrigins = [
  'http://localhost:3000'
  'https://zealous-pebble-08744c900.5.azurestaticapps.net'
]

param entraTenantId = 'f3cd06b0-485e-4550-aa88-25582b420884'
param entraApiClientId = '8e98ac1c-e95c-433a-87a2-729661b8ad85'

param embeddingProvider = 'huggingface'
param embeddingModel = 'BAAI/bge-base-en-v1.5'
param embeddingDimension = '768'

param generationProvider = 'huggingface'
param generationModel = 'Qwen/Qwen3-4B-Instruct-2507:cheapest'

param actionExecutionEnabled = 'false'
param actionExecutionMode = 'dry_run'
param actionExecutionLiveAllowlist = 'update_case_status'

param mcpPublicHostname = 'casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io'
param investigationUseMcp = 'true'
param mcpClientUrl = 'http://127.0.0.1:8000/mcp/'
param mcpClientTimeoutSeconds = '120'

param databaseUrlSecret = readEnvironmentVariable('CASEMESH_DATABASE_URL_SECRET')
param hfTokenSecret = readEnvironmentVariable('CASEMESH_HF_TOKEN_SECRET')
param mcpAuthTokenSecret = readEnvironmentVariable('CASEMESH_MCP_AUTH_TOKEN_SECRET')
param microsoftProviderAuthenticationSecret = readEnvironmentVariable('CASEMESH_MICROSOFT_AUTH_SECRET')