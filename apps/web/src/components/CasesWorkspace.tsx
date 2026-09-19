import {
  useEffect,
  useMemo,
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


function humanize(
  value: string,
): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    )
}


function isClosedCase(
  status: string,
): boolean {
  const normalized =
    status.toLowerCase()

  return (
    normalized === "closed" ||
    normalized === "resolved" ||
    normalized === "completed"
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


  const activeCount =
    useMemo(
      () =>
        cases.filter(
          (item) =>
            !isClosedCase(
              item.status,
            ),
        ).length,
      [cases],
    )

  const highPriorityCount =
    useMemo(
      () =>
        cases.filter(
          (item) => {
            const priority =
              item.priority.toLowerCase()

            return (
              priority === "high" ||
              priority === "critical"
            )
          },
        ).length,
      [cases],
    )


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
            Read each case as a short operational
            story: what happened, where it stands,
            and what deserves attention next.
          </p>
        </div>

        <div className="case-count">
          {cases.length}
          <span>Cases</span>
        </div>
      </div>

      {!loading &&
        !error &&
        cases.length > 0 && (
          <section className="workspace-story-metrics">
            <article>
              <span>TOTAL CASES</span>
              <strong>{cases.length}</strong>
              <p>
                Cases currently visible to this
                workspace.
              </p>
            </article>

            <article>
              <span>ACTIVE JOURNEYS</span>
              <strong>{activeCount}</strong>
              <p>
                Cases that have not reached a
                terminal state.
              </p>
            </article>

            <article>
              <span>HIGH ATTENTION</span>
              <strong>
                {highPriorityCount}
              </strong>
              <p>
                High or critical priority cases
                that deserve faster review.
              </p>
            </article>
          </section>
        )}

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
          <div className="case-story-list">
            {cases.map(
              (caseRecord) => (
                <article
                  className="case-story-card"
                  key={caseRecord.id}
                >
                  <div className="case-story-topline">
                    <div>
                      <div className="section-label">
                        {caseRecord.case_number}
                      </div>

                      <h3>
                        {caseRecord.title}
                      </h3>
                    </div>

                    <div className="case-story-badges">
                      <span
                        className={
                          `status-badge status-${caseRecord.status}`
                        }
                      >
                        {humanize(
                          caseRecord.status,
                        )}
                      </span>

                      <span
                        className={
                          `priority-badge priority-${caseRecord.priority}`
                        }
                      >
                        {humanize(
                          caseRecord.priority,
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="case-story-grid">
                    <div>
                      <span>
                        WHAT HAPPENED
                      </span>

                      <p>
                        {caseRecord.description ??
                          "No case description has been recorded yet."}
                      </p>
                    </div>

                    <div>
                      <span>
                        CURRENT STATE
                      </span>

                      <p>
                        {humanize(
                          caseRecord.status,
                        )}
                        {" · "}
                        {humanize(
                          caseRecord.priority,
                        )}
                        {" priority"}
                      </p>
                    </div>

                    <div>
                      <span>
                        LAST MOVEMENT
                      </span>

                      <p>
                        Updated
                        {" "}
                        {formatDate(
                          caseRecord.updated_at,
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="case-story-footer">
                    <div>
                      <span>
                        Customer reference
                      </span>

                      <strong>
                        {caseRecord.customer_ref ??
                          "Not provided"}
                      </strong>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        onOpenCase(
                          caseRecord,
                        )
                      }
                    >
                      Open Case Story
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
