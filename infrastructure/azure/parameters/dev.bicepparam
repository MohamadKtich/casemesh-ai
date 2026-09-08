using '../main.bicep'

param location = 'uaenorth'

param environmentName = 'casemesh-env-dev'
param containerAppName = 'casemesh-api-dev'

param containerImage = 'mcr.microsoft.com/k8se/quickstart:latest'
param targetPort = 80

param minReplicas = 0
param maxReplicas = 1