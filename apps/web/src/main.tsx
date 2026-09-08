import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { MsalProvider } from "@azure/msal-react"

import "./index.css"

import App from "./App.tsx"
import { msalInstance } from "./auth"


async function bootstrap() {
  await msalInstance.initialize()

  const rootElement =
    document.getElementById("root")

  if (!rootElement) {
    throw new Error(
      "Unable to find the React root element.",
    )
  }

  createRoot(rootElement).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </StrictMode>,
  )
}


void bootstrap()