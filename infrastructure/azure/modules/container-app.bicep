param containerAppName string
param location string
param environmentId string
param containerImage string
param targetPort int = 8000
param minReplicas int = 0
param maxReplicas int = 1
param tags object = {}

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
      }
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
          ]
        }
      ]

      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn