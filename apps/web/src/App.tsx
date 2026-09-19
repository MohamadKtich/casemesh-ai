import {
  InteractionStatus,
} from "@azure/msal-browser"

import {
  useIsAuthenticated,
  useMsal,
} from "@azure/msal-react"

import {
  useEffect,
  useState,
} from "react"

import "./App.css"

import ActionsWorkspace from "./components/ActionsWorkspace"
import CaseMeshLogo from "./components/CaseMeshLogo"
import ApprovalsWorkspace from "./components/ApprovalsWorkspace"
import CasesWorkspace from "./components/CasesWorkspace"
import EvidenceWorkspace from "./components/EvidenceWorkspace"
import EvaluationWorkspace from "./components/EvaluationWorkspace"
import InvestigationsWorkspace from "./components/InvestigationsWorkspace"

import {
  loginRequest,
} from "./auth"

import {
  getApiRoot,
  getHealthReady,
  type ApiRootResponse,
  type CaseRecord,
} from "./lib/api"


type ConnectionState =
  | "checking"
  | "online"
  | "offline"


type ActiveView =
  | "overview"
  | "cases"
  | "evidence"
  | "investigations"
  | "approvals"
  | "actions"
  | "evaluation"


type ThemeMode =
  | "dark"
  | "light"


function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark"
  }

  const saved =
    window.localStorage.getItem(
      "casemesh-theme",
    )

  if (
    saved === "dark" ||
    saved === "light"
  ) {
    return saved
  }

  return window.matchMedia(
    "(prefers-color-scheme: light)",
  ).matches
    ? "light"
    : "dark"
}


function humanizeValue(
  value: string,
): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    )
}


function caseNextStep(
  status: string,
): string {
  const normalized =
    status.toLowerCase()

  if (
    normalized === "action_executed" ||
    normalized === "executed" ||
    normalized === "resolved"
  ) {
    return "Review the execution audit trail and outcome, then close the case or continue only if follow-up work remains."
  }

  if (
    normalized === "awaiting_approval" ||
    normalized === "pending_approval"
  ) {
    return "Review the governed action request and record the required human approval decision."
  }

  if (
    normalized === "investigating" ||
    normalized === "under_investigation"
  ) {
    return "Continue the investigation, verify grounded evidence, and resolve any evidence gaps before proposing an action."
  }

  if (
    normalized === "new" ||
    normalized === "open"
  ) {
    return "Add supporting evidence and start a grounded investigation before making a case decision."
  }

  if (normalized === "closed") {
    return "This case is closed. Review the audit history only if follow-up or reopening is required."
  }

  return "Continue through evidence, investigation, approval, and controlled action according to the current case state."
}


function App() {
  const {
    instance,
    accounts,
    inProgress,
  } = useMsal()

  const isAuthenticated =
    useIsAuthenticated()

  const account =
    accounts[0] ?? null

  const authBusy =
    inProgress !== InteractionStatus.None

  const authDisplayName =
    account?.name ??
    account?.username ??
    "Signed-in user"

  const authUsername =
    account?.username ?? ""


  const [
    connectionState,
    setConnectionState,
  ] = useState<ConnectionState>(
    "checking",
  )

  const [
    apiInfo,
    setApiInfo,
  ] = useState<ApiRootResponse | null>(
    null,
  )

  const [
    errorMessage,
    setErrorMessage,
  ] = useState<string | null>(
    null,
  )

  const [
    activeView,
    setActiveView,
  ] = useState<ActiveView>(
    "overview",
  )

  const [
    selectedCase,
    setSelectedCase,
  ] = useState<CaseRecord | null>(
    null,
  )

  const [
    theme,
    setTheme,
  ] = useState<ThemeMode>(
    getInitialTheme,
  )


  useEffect(() => {
    document.documentElement.dataset.theme =
      theme

    document.documentElement.style.colorScheme =
      theme

    window.localStorage.setItem(
      "casemesh-theme",
      theme,
    )
  }, [theme])


  useEffect(() => {
    const controller =
      new AbortController()

    async function checkBackendHealth() {
      try {
        setConnectionState(
          "checking",
        )

        await getHealthReady(
          controller.signal,
        )

        setConnectionState(
          "online",
        )

        setErrorMessage(
          null,
        )
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return
        }

        setConnectionState(
          "offline",
        )

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Unable to reach CaseMesh API.",
        )
      }
    }

    void checkBackendHealth()

    return () => {
      controller.abort()
    }
  }, [])


  useEffect(() => {
    const controller =
      new AbortController()

    if (
      !isAuthenticated ||
      authBusy
    ) {
      return () => {
        controller.abort()
      }
    }

    async function loadApiInfo() {
      try {
        const data =
          await getApiRoot(
            controller.signal,
          )

        setApiInfo(
          data,
        )
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return
        }

        setApiInfo(
          null,
        )

        console.error(
          "Unable to load authenticated API metadata.",
          error,
        )
      }
    }

    void loadApiInfo()

    return () => {
      controller.abort()
    }
  }, [
    isAuthenticated,
    authBusy,
  ])


  const visibleApiInfo =
    isAuthenticated && !authBusy
      ? apiInfo
      : null

  const visibleActiveView: ActiveView =
    isAuthenticated
      ? activeView
      : "overview"

  const visibleSelectedCase =
    isAuthenticated
      ? selectedCase
      : null


  const connectionLabel =
    connectionState === "online"
      ? "Connected"
      : connectionState === "offline"
        ? "Unavailable"
        : "Checking"

  const viewKey =
    `${visibleActiveView}:${visibleSelectedCase?.id ?? "root"}`


  function toggleTheme() {
    setTheme(
      (current) =>
        current === "dark"
          ? "light"
          : "dark",
    )
  }


  function handleSignIn() {
    if (authBusy) {
      return
    }

    setActiveView(
      "overview",
    )

    setSelectedCase(
      null,
    )

    setApiInfo(
      null,
    )

    void instance.loginRedirect(
      loginRequest,
    )
  }


  function handleSignOut() {
    if (authBusy) {
      return
    }

    setActiveView(
      "overview",
    )

    setSelectedCase(
      null,
    )

    setApiInfo(
      null,
    )

    if (account) {
      void instance.logoutRedirect({
        account,
        postLogoutRedirectUri:
          window.location.origin,
      })

      return
    }

    void instance.logoutRedirect({
      postLogoutRedirectUri:
        window.location.origin,
    })
  }


  function openOverview() {
    setActiveView(
      "overview",
    )

    setSelectedCase(
      null,
    )
  }


  function openCases() {
    if (!isAuthenticated) {
      return
    }

    setActiveView(
      "cases",
    )

    setSelectedCase(
      null,
    )
  }


  function openCase(
    caseRecord: CaseRecord,
  ) {
    if (!isAuthenticated) {
      return
    }

    setSelectedCase(
      caseRecord,
    )

    setActiveView(
      "cases",
    )
  }


  function openEvidence() {
    if (!isAuthenticated) {
      return
    }

    if (!selectedCase) {
      setActiveView(
        "cases",
      )

      return
    }

    setActiveView(
      "evidence",
    )
  }


  function openInvestigations() {
    if (!isAuthenticated) {
      return
    }

    if (!selectedCase) {
      setActiveView(
        "cases",
      )

      return
    }

    setActiveView(
      "investigations",
    )
  }


  function openApprovals() {
    if (!isAuthenticated) {
      return
    }

    if (!selectedCase) {
      setActiveView(
        "cases",
      )

      return
    }

    setActiveView(
      "approvals",
    )
  }


  function openActions() {
    if (!isAuthenticated) {
      return
    }

    if (!selectedCase) {
      setActiveView(
        "cases",
      )

      return
    }

    setActiveView(
      "actions",
    )
  }


  function openEvaluation() {
    if (!isAuthenticated) {
      return
    }

    setActiveView(
      "evaluation",
    )

    setSelectedCase(
      null,
    )
  }

  function backToSelectedCase() {
    if (!isAuthenticated) {
      setActiveView(
        "overview",
      )

      setSelectedCase(
        null,
      )

      return
    }

    setActiveView(
      "cases",
    )
  }


  function renderOverview() {
    return (
      <>
        <section className="hero-panel">
          <div className="hero-copy">
            <div className="section-label">
              CASEMESH CONTROL PLANE
            </div>

            <h2>
              Investigate evidence.
              <br />
              Ground decisions.
              <br />
              Control actions.
            </h2>

            <p>
              Evidence-grounded case analysis
              powered by RAG, LangGraph,
              MCP tools, human approval,
              and controlled execution.
            </p>
          </div>

          <div className="architecture-card">
            <div className="architecture-title">
              Active Architecture
            </div>

            <div className="flow">
              <div className="flow-node">
                LangGraph Agent
              </div>

              <div className="flow-line" />

              <div className="flow-node">
                Authenticated MCP
              </div>

              <div className="flow-line" />

              <div className="flow-node">
                Hybrid RAG
              </div>

              <div className="flow-line" />

              <div className="flow-node">
                Azure PostgreSQL
              </div>
            </div>
          </div>
        </section>

        <section className="metrics-grid">
          <article className="metric-card">
            <div className="metric-label">
              API STATUS
            </div>

            <div className="metric-value">
              {connectionLabel}
            </div>

            <div className="metric-detail">
              {visibleApiInfo?.service ??
                "CaseMesh API"}
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-label">
              API VERSION
            </div>

            <div className="metric-value">
              {visibleApiInfo?.version ??
                (isAuthenticated
                  ? "Loading"
                  : "Protected")}
            </div>

            <div className="metric-detail">
              Azure Container Apps
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-label">
              IDENTITY
            </div>

            <div className="metric-value">
              {isAuthenticated
                ? "Authenticated"
                : "Anonymous"}
            </div>

            <div className="metric-detail">
              Microsoft Entra ID
            </div>
          </article>

          <article className="metric-card">
            <div className="metric-label">
              EXECUTION
            </div>

            <div className="metric-value">
              Guarded
            </div>

            <div className="metric-detail">
              Policy + HITL protected
            </div>
          </article>
        </section>

        <section className="workspace-grid">
          <article className="workspace-card">
            <div className="card-heading">
              <div>
                <div className="section-label">
                  SYSTEM
                </div>

                <h3>
                  Backend Connection
                </h3>
              </div>

              <span
                className={
                  `connection-pill compact ${connectionState}`
                }
              >
                {connectionLabel}
              </span>
            </div>

            <div className="connection-details">
              <div>
                <span>Service</span>

                <strong>
                  {visibleApiInfo?.service ??
                    "CaseMesh API"}
                </strong>
              </div>

              <div>
                <span>Version</span>

                <strong>
                  {visibleApiInfo?.version ??
                    (isAuthenticated
                      ? "Loading"
                      : "Protected")}
                </strong>
              </div>

              <div>
                <span>Status</span>

                <strong>
                  {connectionState === "online"
                    ? "ready"
                    : connectionState}
                </strong>
              </div>

              <div>
                <span>
                  MCP Endpoint
                </span>

                <strong>
                  {visibleApiInfo?.mcp ??
                    "/mcp/"}
                </strong>
              </div>
            </div>

            {errorMessage && (
              <div className="error-panel">
                {errorMessage}
              </div>
            )}
          </article>

          <article className="workspace-card">
            <div className="card-heading">
              <div>
                <div className="section-label">
                  SECURITY
                </div>

                <h3>
                  Safety Controls
                </h3>
              </div>
            </div>

            <div className="safety-list">
              <div className="safety-row">
                <span className="safety-check">
                  OK
                </span>

                <div>
                  <strong>
                    Microsoft Entra ID
                  </strong>

                  <p>
                    Browser sign-in and
                    delegated API scope configured.
                  </p>
                </div>
              </div>

              <div className="safety-row">
                <span className="safety-check">
                  OK
                </span>

                <div>
                  <strong>
                    MCP Authentication
                  </strong>

                  <p>
                    Bearer-protected
                    Streamable HTTP.
                  </p>
                </div>
              </div>

              <div className="safety-row">
                <span className="safety-check">
                  OK
                </span>

                <div>
                  <strong>
                    Human Approval
                  </strong>

                  <p>
                    Sensitive actions require
                    HITL review.
                  </p>
                </div>
              </div>

              <div className="safety-row">
                <span className="safety-check">
                  OK
                </span>

                <div>
                  <strong>
                    Controlled Execution
                  </strong>

                  <p>
                    Live actions remain
                    allowlisted and guarded.
                  </p>
                </div>
              </div>
            </div>
          </article>
        </section>
      </>
    )
  }


  function renderCaseDetails(
    caseRecord: CaseRecord,
  ) {
    return (
      <section className="case-detail-workspace">
        <button
          className="back-button"
          type="button"
          onClick={() =>
            setSelectedCase(
              null,
            )
          }
        >
          Back to Cases
        </button>

        <section className="story-hero case-story-hero">
          <div>
            <div className="section-label">
              CASE STORY
            </div>

            <h2>
              {caseRecord.case_number}
            </h2>

            <p>
              {caseRecord.title}
            </p>
          </div>

          <div className="case-detail-badges">
            <span
              className={
                `status-badge status-${caseRecord.status}`
              }
            >
              {humanizeValue(
                caseRecord.status,
              )}
            </span>

            <span
              className={
                `priority-badge priority-${caseRecord.priority}`
              }
            >
              {humanizeValue(
                caseRecord.priority,
              )}
            </span>
          </div>
        </section>

        <div className="story-grid case-overview-story">
          <article className="story-card story-card-accent">
            <div className="story-step">
              01
            </div>

            <div className="section-label">
              WHAT HAPPENED
            </div>

            <h4>
              Case context
            </h4>

            <p className="story-copy">
              {caseRecord.description ??
                "No description has been recorded for this case yet."}
            </p>
          </article>

          <article className="story-card">
            <div className="story-step">
              02
            </div>

            <div className="section-label">
              WHERE IT STANDS
            </div>

            <h4>
              Current operating state
            </h4>

            <p className="story-copy">
              This case is currently
              {" "}
              {humanizeValue(
                caseRecord.status,
              )}
              {" "}
              with
              {" "}
              {humanizeValue(
                caseRecord.priority,
              )}
              {" "}
              priority.
            </p>

            <div className="story-next-meta">
              <span>Created</span>
              <strong>
                {new Date(
                  caseRecord.created_at,
                ).toLocaleString()}
              </strong>

              <span>Last updated</span>
              <strong>
                {new Date(
                  caseRecord.updated_at,
                ).toLocaleString()}
              </strong>
            </div>
          </article>

          <article className="story-card">
            <div className="story-step">
              03
            </div>

            <div className="section-label">
              IDENTITY
            </div>

            <h4>
              Who and what this case refers to
            </h4>

            <p className="story-copy">
              Customer reference:
              {" "}
              {caseRecord.customer_ref ??
                "Not provided"}.
            </p>

            <div className="story-next-meta">
              <span>Case ID</span>
              <strong>
                {caseRecord.id}
              </strong>

              <span>Case number</span>
              <strong>
                {caseRecord.case_number}
              </strong>
            </div>
          </article>

          <article className="story-card story-next-action">
            <div className="story-step">
              04
            </div>

            <div className="section-label">
              NEXT PATH
            </div>

            <h4>
              Recommended next step
            </h4>

            <p className="story-copy">
              {caseNextStep(
                caseRecord.status,
              )}
            </p>
          </article>
        </div>

        <section className="case-journey">
          <button
            type="button"
            className="case-journey-step"
            onClick={openEvidence}
          >
            <span>01</span>
            <strong>Evidence</strong>
            <small>
              Add and retrieve supporting sources
            </small>
          </button>

          <button
            type="button"
            className="case-journey-step"
            onClick={openInvestigations}
          >
            <span>02</span>
            <strong>Investigate</strong>
            <small>
              Build grounded findings and citations
            </small>
          </button>

          <button
            type="button"
            className="case-journey-step"
            onClick={openApprovals}
          >
            <span>03</span>
            <strong>Approve</strong>
            <small>
              Review policy-governed decisions
            </small>
          </button>

          <button
            type="button"
            className="case-journey-step"
            onClick={openActions}
          >
            <span>04</span>
            <strong>Act safely</strong>
            <small>
              Simulate controlled execution
            </small>
          </button>
        </section>
      </section>
    )
  }


  function pageTitle(): string {
    if (visibleActiveView === "overview") {
      return "Case Intelligence"
    }

    if (visibleActiveView === "evidence") {
      return visibleSelectedCase
        ? `${visibleSelectedCase.case_number} Evidence`
        : "Evidence"
    }

    if (visibleActiveView === "investigations") {
      return visibleSelectedCase
        ? `${visibleSelectedCase.case_number} Investigations`
        : "Investigations"
    }

    if (visibleActiveView === "approvals") {
      return visibleSelectedCase
        ? `${visibleSelectedCase.case_number} Approvals`
        : "Approvals"
    }

    if (visibleActiveView === "evaluation") {
      return "Evaluation"
    }
    if (visibleActiveView === "actions") {
      return visibleSelectedCase
        ? `${visibleSelectedCase.case_number} Actions`
        : "Actions"
    }

    if (visibleSelectedCase) {
      return visibleSelectedCase.case_number
    }

    return "Cases"
  }


  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <CaseMeshLogo />
          </div>

          <div>
            <div className="brand-name">
              CaseMesh AI
            </div>

            <div className="brand-subtitle">
              Agentic Case Intelligence
            </div>
          </div>
        </div>

        <nav className="navigation">
          <button
            className={
              visibleActiveView === "overview"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openOverview}
          >
            <span>01</span>
            Overview
          </button>

          <button
            className={
              visibleActiveView === "cases"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openCases}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Cases"
                : "Sign in with Microsoft to access Cases."
            }
          >
            <span>02</span>
            Cases
          </button>

          <button
            className={
              visibleActiveView === "evidence"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openEvidence}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Evidence"
                : "Sign in with Microsoft to access Evidence."
            }
          >
            <span>03</span>
            Evidence
          </button>

          <button
            className={
              visibleActiveView === "investigations"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openInvestigations}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Investigations"
                : "Sign in with Microsoft to access Investigations."
            }
          >
            <span>04</span>
            Investigations
          </button>

          <button
            className={
              visibleActiveView === "approvals"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openApprovals}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Approvals"
                : "Sign in with Microsoft to access Approvals."
            }
          >
            <span>05</span>
            Approvals
          </button>

          <button
            className={
              visibleActiveView === "actions"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openActions}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Actions"
                : "Sign in with Microsoft to access Actions."
            }
          >
            <span>06</span>
            Actions
          </button>

          <button
            className={
              visibleActiveView === "evaluation"
                ? "nav-item active"
                : "nav-item"
            }
            type="button"
            onClick={openEvaluation}
            disabled={!isAuthenticated}
            aria-disabled={!isAuthenticated}
            title={
              isAuthenticated
                ? "Evaluation"
                : "Sign in with Microsoft to access Evaluation."
            }
          >
            <span>07</span>
            Evaluation          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="environment-label">
            Environment
          </div>

          <div className="environment-value">
            Azure Development
          </div>

          <div className="sidebar-auth-state">
            <span
              className={
                isAuthenticated
                  ? "auth-state-dot authenticated"
                  : "auth-state-dot"
              }
            />

            {isAuthenticated
              ? "Entra authenticated"
              : "Entra sign-in required"}
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              OPERATIONS CONSOLE
            </div>

            <h1>
              {pageTitle()}
            </h1>
          </div>

          <div className="topbar-actions">
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={
                theme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
              title={
                theme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
            >
              <span
                className="theme-toggle-icon"
                aria-hidden="true"
              >
                {theme === "dark"
                  ? "☼"
                  : "◐"}
              </span>

              <span className="theme-toggle-copy">
                {theme === "dark"
                  ? "Light"
                  : "Dark"}
              </span>
            </button>

            <div
              className={
                `connection-pill ${connectionState}`
              }
            >
              <span className="status-dot" />
              {connectionLabel}
            </div>

            <div className="auth-panel">
              {isAuthenticated ? (
                <>
                  <div className="auth-identity">
                    <div className="auth-status-label">
                      MICROSOFT ENTRA
                    </div>

                    <strong>
                      {authDisplayName}
                    </strong>

                    {authUsername && (
                      <span>
                        {authUsername}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    className="auth-button secondary"
                    disabled={authBusy}
                    onClick={handleSignOut}
                  >
                    {authBusy
                      ? "Working..."
                      : "Sign out"}
                  </button>
                </>
              ) : (
                <>
                  <div className="auth-identity">
                    <div className="auth-status-label">
                      MICROSOFT ENTRA
                    </div>

                    <strong>
                      Not signed in
                    </strong>

                    <span>
                      Secure operator identity
                    </span>
                  </div>

                  <button
                    type="button"
                    className="auth-button"
                    disabled={authBusy}
                    onClick={handleSignIn}
                  >
                    {authBusy
                      ? "Signing in..."
                      : "Sign in with Microsoft"}
                  </button>
                </>
              )}
            </div>
          </div>
        </header>

        <div
          key={viewKey}
          className="view-stage"
        >
          {visibleActiveView === "overview" &&
            renderOverview()}

          {isAuthenticated &&
            visibleActiveView === "cases" &&
            !visibleSelectedCase && (
              <CasesWorkspace
                onOpenCase={openCase}
              />
            )}

          {isAuthenticated &&
            visibleActiveView === "cases" &&
            selectedCase &&
            renderCaseDetails(
              selectedCase,
            )}

          {isAuthenticated &&
            visibleActiveView === "evidence" &&
            visibleSelectedCase && (
              <EvidenceWorkspace
                caseRecord={visibleSelectedCase}
                onBack={backToSelectedCase}
              />
            )}

          {isAuthenticated &&
            visibleActiveView === "investigations" &&
            visibleSelectedCase && (
              <InvestigationsWorkspace
                caseRecord={visibleSelectedCase}
                onBack={backToSelectedCase}
              />
            )}

          {isAuthenticated &&
            visibleActiveView === "approvals" &&
            visibleSelectedCase && (
              <ApprovalsWorkspace
                caseRecord={visibleSelectedCase}
                onBack={backToSelectedCase}
              />
            )}

          {isAuthenticated &&
            visibleActiveView === "evaluation" && (
              <EvaluationWorkspace />
            )}

          {isAuthenticated &&
            visibleActiveView === "actions" &&
            visibleSelectedCase && (
              <ActionsWorkspace
                caseRecord={visibleSelectedCase}
                onBack={backToSelectedCase}
              />
            )}
        </div>
      </main>
    </div>
  )
}


export default App
