import {
  useEffect,
  useState,
} from "react"

import {
  getCases,
  type CaseRecord,
} from "../lib/api"


interface CasesWorkspaceProps {
  onOpenCase: (
    caseRecord: CaseRecord,
  ) => void
}


function formatDate(
  value: string,
): string {
  return new Intl.DateTimeFormat(
    "en",
    {
      year: "numeric",
      month: "short",
      day: "2-digit",
    },
  ).format(
    new Date(value),
  )
}


function CasesWorkspace({
  onOpenCase,
}: CasesWorkspaceProps) {
  const [
    cases,
    setCases,
  ] = useState<CaseRecord[]>([])

  const [
    loading,
    setLoading,
  ] = useState(true)

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )

  useEffect(() => {
    const controller =
      new AbortController()

    async function loadCases() {
      try {
        setLoading(true)

        const data =
          await getCases(
            controller.signal,
          )

        setCases(data)
        setError(null)
      } catch (loadError) {
        if (
          loadError instanceof DOMException &&
          loadError.name === "AbortError"
        ) {
          return
        }

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load cases.",
        )
      } finally {
        setLoading(false)
      }
    }

    void loadCases()

    return () => {
      controller.abort()
    }
  }, [])


  return (
    <section className="cases-workspace">
      <div className="workspace-header">
        <div>
          <div className="section-label">
            CASE MANAGEMENT
          </div>

          <h2>
            Cases
          </h2>

          <p>
            Review active cases,
            evidence state, priority,
            and investigation status.
          </p>
        </div>

        <div className="case-count">
          {cases.length}
          <span>Cases</span>
        </div>
      </div>

      {loading && (
        <div className="empty-state">
          Loading cases...
        </div>
      )}

      {error && (
        <div className="error-panel">
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        cases.length === 0 && (
          <div className="empty-state">
            No cases available.
          </div>
        )}

      {!loading &&
        !error &&
        cases.length > 0 && (
          <div className="cases-table">
            <div className="cases-table-head">
              <span>Case</span>
              <span>Status</span>
              <span>Priority</span>
              <span>Updated</span>
              <span />
            </div>

            {cases.map(
              (caseRecord) => (
                <article
                  className="case-row"
                  key={caseRecord.id}
                >
                  <div className="case-main">
                    <strong>
                      {caseRecord.case_number}
                    </strong>

                    <span>
                      {caseRecord.title}
                    </span>
                  </div>

                  <div>
                    <span
                      className={
                        `status-badge status-${caseRecord.status}`
                      }
                    >
                      {caseRecord.status}
                    </span>
                  </div>

                  <div>
                    <span
                      className={
                        `priority-badge priority-${caseRecord.priority}`
                      }
                    >
                      {caseRecord.priority}
                    </span>
                  </div>

                  <div className="case-date">
                    {formatDate(
                      caseRecord.updated_at,
                    )}
                  </div>

                  <div className="case-action">
                    <button
                      type="button"
                      onClick={() =>
                        onOpenCase(
                          caseRecord,
                        )
                      }
                    >
                      Open Case
                    </button>
                  </div>
                </article>
              ),
            )}
          </div>
        )}
    </section>
  )
}


export default CasesWorkspace