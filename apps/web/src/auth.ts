import {
  PublicClientApplication,
  type Configuration,
  type RedirectRequest,
} from "@azure/msal-browser"


function requireEnv(
  name: string,
  value: string | undefined,
): string {
  const normalized = value?.trim()

  if (!normalized) {
    throw new Error(
      `Missing required frontend environment variable: ${name}`,
    )
  }

  return normalized
}


export const ENTRA_TENANT_ID = requireEnv(
  "VITE_ENTRA_TENANT_ID",
  import.meta.env.VITE_ENTRA_TENANT_ID,
)


export const ENTRA_WEB_CLIENT_ID = requireEnv(
  "VITE_ENTRA_CLIENT_ID",
  import.meta.env.VITE_ENTRA_CLIENT_ID,
)


export const ENTRA_API_CLIENT_ID = requireEnv(
  "VITE_ENTRA_API_CLIENT_ID",
  import.meta.env.VITE_ENTRA_API_CLIENT_ID,
)


export const API_ACCESS_SCOPE =
  `api://${ENTRA_API_CLIENT_ID}/access_as_user`


const msalConfig: Configuration = {
  auth: {
    clientId: ENTRA_WEB_CLIENT_ID,
    authority:
      `https://login.microsoftonline.com/${ENTRA_TENANT_ID}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },

  cache: {
    cacheLocation: "sessionStorage",
  },
}


export const msalInstance =
  new PublicClientApplication(msalConfig)


export const loginRequest: RedirectRequest = {
  scopes: [
    "openid",
    "profile",
    "email",
    API_ACCESS_SCOPE,
  ],
}


export const apiScopes = [
  API_ACCESS_SCOPE,
]