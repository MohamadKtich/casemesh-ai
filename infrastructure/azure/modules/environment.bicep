param environmentName string
param location string
param tags object = {}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: environmentName
  location: location
  tags: tags

  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }

    peerAuthentication: {
      mtls: {
        enabled: false
      }
    }

    peerTrafficConfiguration: {
      encryption: {
        enabled: false
      }
    }

    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
  }
}

output environmentId string = containerAppsEnvironment.id
output environmentName string = containerAppsEnvironment.name
output defaultDomain string = containerAppsEnvironment.properties.defaultDomain