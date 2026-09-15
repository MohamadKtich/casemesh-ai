@description('Name of the user-assigned managed identity used by the CaseMesh API.')
param managedIdentityName string

@description('Azure region for the managed identity.')
param location string

@description('Common CaseMesh resource tags.')
param tags object = {}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: managedIdentityName
  location: location
  tags: tags
}

output managedIdentityId string = managedIdentity.id
output managedIdentityName string = managedIdentity.name
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
