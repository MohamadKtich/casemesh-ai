targetScope = 'resourceGroup'

@description('Azure region used for CaseMesh resources.')
param location string = resourceGroup().location

@description('Container Apps environment name.')
param environmentName string = 'casemesh-env-dev'

@description('CaseMesh API Container App name.')
param containerAppName string = 'casemesh-api-dev'

@description('Container image used for infrastructure validation.')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Port exposed by the container image.')
@minValue(1)
@maxValue(65535)
param targetPort int = 80

@description('Minimum number of running replicas.')
@minValue(0)
param minReplicas int = 0

@description('Maximum number of running replicas.')
@minValue(1)
param maxReplicas int = 1

var commonTags = {
  project: 'CaseMesh-AI'
  environment: 'dev'
  managedBy: 'Bicep'
  phase: '27'
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
    tags: commonTags
  }
}

output environmentName string = environment.outputs.environmentName
output containerAppName string = api.outputs.containerAppName
output containerAppUrl string = 'https://${api.outputs.fqdn}'