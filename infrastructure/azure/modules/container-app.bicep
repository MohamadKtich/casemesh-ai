param containerAppName string
param location string
param environmentId string

param containerImage string
param targetPort int = 8000

param minReplicas int = 0
param maxReplicas int = 1

param corsAllowedOrigins array

param entraTenantId string
param entraApiClientId string

param embeddingProvider string
param embeddingModel string
param embeddingDimension string

param generationProvider string
param generationModel string

param actionExecutionEnabled string
param actionExecutionMode string
param actionExecutionLiveAllowlist string

param mcpPublicHostname string
param investigationUseMcp string
param mcpClientUrl string
param mcpClientTimeoutSeconds string

@secure()
param databaseUrlSecret string

@secure()
param hfTokenSecret string

@secure()
param mcpAuthTokenSecret string

@secure()
param microsoftProviderAuthenticationSecret string

param tags object = {}

var corsAllowedOriginsCsv = join(corsAllowedOrigins, ',')

resource containerApp 'Microsoft.App/containerApps@2026-01-01' = {
  name: containerAppName
  location: location
  tags: tags

  properties: {
    environmentId: environmentId

    configuration: {
      activeRevisionsMode: 'Single'

      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false

        corsPolicy: {
          allowCredentials: false

          allowedOrigins: corsAllowedOrigins

          allowedMethods: [
            'GET'
            'POST'
            'PUT'
            'PATCH'
            'DELETE'
            'OPTIONS'
          ]

          allowedHeaders: [
            'Authorization'
            'Content-Type'
            'Accept'
          ]
        }
      }

      secrets: [
        {
          name: 'hf-token'
          value: hfTokenSecret
        }
        {
          name: 'mcp-auth-token'
          value: mcpAuthTokenSecret
        }
        {
          name: 'database-url'
          value: databaseUrlSecret
        }
        {
          name: 'microsoft-provider-authentication-secret'
          value: microsoftProviderAuthenticationSecret
        }
      ]
    }

    template: {
      containers: [
        {
          name: 'casemesh-api'
          image: containerImage

          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }

          env: [
            {
              name: 'APP_ENV'
              value: 'cloud'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'EMBEDDING_PROVIDER'
              value: embeddingProvider
            }
            {
              name: 'EMBEDDING_MODEL'
              value: embeddingModel
            }
            {
              name: 'EMBEDDING_DIMENSION'
              value: embeddingDimension
            }
            {
              name: 'HF_TOKEN'
              secretRef: 'hf-token'
            }
            {
              name: 'GENERATION_PROVIDER'
              value: generationProvider
            }
            {
              name: 'GENERATION_MODEL'
              value: generationModel
            }
            {
              name: 'ACTION_EXECUTION_ENABLED'
              value: actionExecutionEnabled
            }
            {
              name: 'ACTION_EXECUTION_MODE'
              value: actionExecutionMode
            }
            {
              name: 'ACTION_EXECUTION_LIVE_ALLOWLIST'
              value: actionExecutionLiveAllowlist
            }
            {
              name: 'MCP_AUTH_TOKEN'
              secretRef: 'mcp-auth-token'
            }
            {
              name: 'MCP_PUBLIC_HOSTNAME'
              value: mcpPublicHostname
            }
            {
              name: 'INVESTIGATION_USE_MCP'
              value: investigationUseMcp
            }
            {
              name: 'MCP_CLIENT_URL'
              value: mcpClientUrl
            }
            {
              name: 'MCP_CLIENT_TIMEOUT_SECONDS'
              value: mcpClientTimeoutSeconds
            }
            {
              name: 'CORS_ALLOWED_ORIGINS'
              value: corsAllowedOriginsCsv
            }
          ]
        }
      ]

      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        cooldownPeriod: 300
        pollingInterval: 30
      }
    }
  }
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2026-01-01' = {
  parent: containerApp
  name: 'current'

  properties: {
    platform: {
      enabled: true
    }

    globalValidation: {
      excludedPaths: [
        '/health/*'
        '/mcp/*'
      ]

      unauthenticatedClientAction: 'Return401'
    }

    identityProviders: {
      azureActiveDirectory: {
        enabled: true

        registration: {
          clientId: entraApiClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
        }
      }
    }

    login: {
      preserveUrlFragmentsForLogins: false
    }
  }
}

output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn