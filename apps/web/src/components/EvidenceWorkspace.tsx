import {
  useEffect,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react"

import {
  embedDocument,
  getDocumentChunks,
  getDocuments,
  ingestDocument,
  searchEvidence,
  uploadDocument,
  type CaseRecord,
  type DocumentChunkRecord,
  type DocumentRecord,
  type RetrievalSearchResponse,
} from "../lib/api"


interface EvidenceWorkspaceProps {
  caseRecord: CaseRecord
  onBack: () => void
}


function formatBytes(
  bytes: number,
): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  return `${(bytes / 1024).toFixed(1)} KB`
}


function formatScore(
  value: number | null,
): string {
  if (value === null) {
    return "N/A"
  }

  return value.toFixed(6)
}


function formatSimilarity(
  value: number | null,
): string {
  if (value === null) {
    return "N/A"
  }

  return `${(value * 100).toFixed(2)}%`
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


function evidenceStage(
  document: DocumentRecord,
): string {
  if (document.ingestion_error) {
    return "Processing needs attention"
  }

  if (
    document.ingestion_status === "ready" ||
    document.ingestion_status === "embedded"
  ) {
    return "Ready for retrieval"
  }

  if (
    document.ingestion_status === "ingested" ||
    document.parser_name
  ) {
    return "Parsed and structured"
  }

  return "Evidence received"
}


function EvidenceWorkspace({
  caseRecord,
  onBack,
}: EvidenceWorkspaceProps) {
  const [
    documents,
    setDocuments,
  ] = useState<DocumentRecord[]>([])

  const [
    selectedDocument,
    setSelectedDocument,
  ] = useState<DocumentRecord | null>(
    null,
  )

  const [
    chunks,
    setChunks,
  ] = useState<DocumentChunkRecord[]>([])

  const [
    loadingDocuments,
    setLoadingDocuments,
  ] = useState(true)

  const [
    loadingChunks,
    setLoadingChunks,
  ] = useState(false)

  const [
    selectedFile,
    setSelectedFile,
  ] = useState<File | null>(
    null,
  )

  const [
    uploadRunning,
    setUploadRunning,
  ] = useState(false)

  const [
    uploadStatus,
    setUploadStatus,
  ] = useState<string | null>(
    null,
  )

  const [
    fileInputKey,
    setFileInputKey,
  ] = useState(0)

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  )

  const [
    searchQuery,
    setSearchQuery,
  ] = useState(
    "What database is used in this CaseMesh Azure environment?",
  )

  const [
    searchTopK,
    setSearchTopK,
  ] = useState(5)

  const [
    searchRunning,
    setSearchRunning,
  ] = useState(false)

  const [
    searchResult,
    setSearchResult,
  ] = useState<RetrievalSearchResponse | null>(
    null,
  )

  const [
    searchError,
    setSearchError,
  ] = useState<string | null>(
    null,
  )


  useEffect(() => {
    const controller =
      new AbortController()

    async function loadDocuments() {
      try {
        setLoadingDocuments(true)

        const data =
          await getDocuments(
            caseRecord.id,
            controller.signal,
          )

        setDocuments(data)
        setChunks([])

        if (data.length > 0) {
          setSelectedDocument(
            data[0],
          )
        } else {
          setSelectedDocument(
            null,
          )
        }

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
            : "Unable to load evidence documents.",
        )
      } finally {
        setLoadingDocuments(false)
      }
    }

    void loadDocuments()

    return () => {
      controller.abort()
    }
  }, [caseRecord.id])


  useEffect(() => {
    if (!selectedDocument) {
      return
    }

    const documentId =
      selectedDocument.id

    const controller =
      new AbortController()

    async function loadChunks() {
      try {
        setLoadingChunks(true)

        const data =
          await getDocumentChunks(
            caseRecord.id,
            documentId,
            controller.signal,
          )

        setChunks(data)
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
            : "Unable to load document chunks.",
        )
      } finally {
        setLoadingChunks(false)
      }
    }

    void loadChunks()

    return () => {
      controller.abort()
    }
  }, [
    caseRecord.id,
    selectedDocument,
  ])


  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file =
      event.target.files?.[0] ?? null

    setSelectedFile(file)
    setUploadStatus(null)
    setError(null)
  }


  async function handleUpload() {
    if (!selectedFile) {
      return
    }

    let uploadedDocumentId:
      | string
      | null = null

    try {
      setUploadRunning(true)
      setError(null)

      setUploadStatus(
        "Uploading evidence...",
      )

      const uploaded =
        await uploadDocument(
          caseRecord.id,
          selectedFile,
        )

      uploadedDocumentId =
        uploaded.id

      setUploadStatus(
        "Upload complete. Ingesting document...",
      )

      const ingested =
        await ingestDocument(
          caseRecord.id,
          uploaded.id,
        )

      setUploadStatus(
        "Ingestion complete. Creating embeddings...",
      )

      const embedding =
        await embedDocument(
          caseRecord.id,
          uploaded.id,
        )

      setUploadStatus(
        `Complete. ${embedding.chunks_embedded} chunk(s) embedded with ${embedding.model}.`,
      )

      const refreshed =
        await getDocuments(
          caseRecord.id,
        )

      setDocuments(
        refreshed,
      )

      const refreshedDocument =
        refreshed.find(
          (document) =>
            document.id ===
            uploaded.id,
        )

      setChunks([])

      setSelectedDocument(
        refreshedDocument ??
          ingested,
      )

      setSelectedFile(
        null,
      )

      setFileInputKey(
        (value) => value + 1,
      )

      setSearchResult(
        null,
      )
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Evidence pipeline failed.",
      )

      setUploadStatus(
        "Evidence processing stopped.",
      )

      if (uploadedDocumentId) {
        try {
          const refreshed =
            await getDocuments(
              caseRecord.id,
            )

          setDocuments(
            refreshed,
          )

          const uploaded =
            refreshed.find(
              (document) =>
                document.id ===
                uploadedDocumentId,
            )

          if (uploaded) {
            setChunks([])

            setSelectedDocument(
              uploaded,
            )
          }
        } catch {
          // Preserve the original pipeline error.
        }
      }
    } finally {
      setUploadRunning(false)
    }
  }


  async function handleSearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const query =
      searchQuery.trim()

    if (query.length < 2) {
      setSearchError(
        "Enter at least two characters to search.",
      )

      return
    }

    try {
      setSearchRunning(true)
      setSearchError(null)

      const result =
        await searchEvidence(
          caseRecord.id,
          query,
          searchTopK,
        )

      setSearchResult(
        result,
      )
    } catch (searchFailure) {
      setSearchResult(
        null,
      )

      setSearchError(
        searchFailure instanceof Error
          ? searchFailure.message
          : "Evidence search failed.",
      )
    } finally {
      setSearchRunning(false)
    }
  }


  function selectSearchDocument(
    documentId: string,
  ) {
    const document =
      documents.find(
        (item) =>
          item.id === documentId,
      )

    if (document) {
      setChunks([])

      setSelectedDocument(
        document,
      )
    }
  }


  return (
    <section className="evidence-workspace">
      <button
        className="back-button"
        type="button"
        onClick={onBack}
      >
        Back to Case
      </button>

      <div className="workspace-header">
        <div>
          <div className="section-label">
            EVIDENCE WORKSPACE
          </div>

          <h2>
            Evidence
          </h2>

          <p>
            Documents, parsed evidence,
            embeddings and hybrid retrieval
            attached to {caseRecord.case_number}.
          </p>
        </div>

        <div className="case-count">
          {documents.length}

          <span>
            Documents
          </span>
        </div>
      </div>

      {!loadingDocuments &&
        !error &&
        documents.length > 0 && (
          <section className="workspace-story-metrics">
            <article>
              <span>DOCUMENTS</span>
              <strong>
                {documents.length}
              </strong>
              <p>
                Evidence sources currently attached
                to this case.
              </p>
            </article>

            <article>
              <span>READY SOURCES</span>
              <strong>
                {documents.filter(
                  (document) =>
                    document.ingestion_status === "ready" ||
                    document.ingestion_status === "embedded",
                ).length}
              </strong>
              <p>
                Sources ready to support retrieval
                and grounded reasoning.
              </p>
            </article>

            <article>
              <span>SEARCH MODE</span>
              <strong>
                Hybrid RAG
              </strong>
              <p>
                Semantic and keyword retrieval
                combined with RRF ranking.
              </p>
            </article>
          </section>
        )}

      <section className="evidence-upload-panel">
        <div>
          <div className="section-label">
            ADD EVIDENCE
          </div>

          <h3>
            Upload, ingest and embed
          </h3>

          <p>
            Select a case evidence document.
            CaseMesh will upload it, parse it,
            create chunks, and generate embeddings.
          </p>
        </div>

        <div className="upload-controls">
          <label className="file-picker">
            <span>
              {selectedFile
                ? selectedFile.name
                : "Choose evidence file"}
            </span>

            <input
              key={fileInputKey}
              type="file"
              disabled={uploadRunning}
              onChange={handleFileChange}
            />
          </label>

          {selectedFile && (
            <div className="selected-file-info">
              <strong>
                {selectedFile.name}
              </strong>

              <span>
                {formatBytes(
                  selectedFile.size,
                )}
              </span>
            </div>
          )}

          <button
            className="primary-action-button"
            type="button"
            disabled={
              !selectedFile ||
              uploadRunning
            }
            onClick={() =>
              void handleUpload()
            }
          >
            {uploadRunning
              ? "Processing..."
              : "Upload Evidence"}
          </button>
        </div>

        {uploadStatus && (
          <div
            className={
              uploadRunning
                ? "pipeline-status running"
                : "pipeline-status complete"
            }
          >
            {uploadStatus}
          </div>
        )}
      </section>

      <section className="evidence-upload-panel">
        <div>
          <div className="section-label">
            HYBRID RETRIEVAL
          </div>

          <h3>
            Search case evidence
          </h3>

          <p>
            Search embedded case evidence using
            vector similarity, keyword ranking
            and Reciprocal Rank Fusion.
          </p>
        </div>

        <form
          className="upload-controls"
          onSubmit={
            (event) =>
              void handleSearch(event)
          }
        >
          <input
            type="text"
            value={searchQuery}
            disabled={searchRunning}
            onChange={
              (event) =>
                setSearchQuery(
                  event.target.value,
                )
            }
            placeholder="Ask a question about this case..."
            style={{
              width: "100%",
              boxSizing: "border-box",
              minHeight: "46px",
              padding: "0 14px",
              border: "1px solid #405477",
              borderRadius: "10px",
              background: "#0b1423",
              color: "#dbe4f2",
              fontSize: "12px",
              outline: "none",
            }}
          />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr",
              gap: "10px",
            }}
          >
            <select
              value={searchTopK}
              disabled={searchRunning}
              onChange={
                (event) =>
                  setSearchTopK(
                    Number(
                      event.target.value,
                    ),
                  )
              }
              style={{
                width: "100%",
                minHeight: "42px",
                padding: "0 10px",
                border: "1px solid #2f405d",
                borderRadius: "9px",
                background: "#0d1523",
                color: "#cbd6e7",
                fontSize: "11px",
              }}
            >
              <option value={3}>
                Top 3
              </option>

              <option value={5}>
                Top 5
              </option>

              <option value={10}>
                Top 10
              </option>

              <option value={20}>
                Top 20
              </option>
            </select>

            <button
              className="primary-action-button"
              type="submit"
              disabled={
                searchRunning ||
                searchQuery.trim().length < 2
              }
            >
              {searchRunning
                ? "Searching..."
                : "Search Evidence"}
            </button>
          </div>
        </form>

        {searchError && (
          <div className="error-panel">
            {searchError}
          </div>
        )}

        {searchResult && (
          <div className="pipeline-status complete">
            {searchResult.results.length}
            {" "}
            result(s) returned using
            {" "}
            {searchResult.mode}
            {" "}
            with
            {" "}
            {searchResult.embedding_model}.
          </div>
        )}
      </section>

      {searchResult && (
        <section className="document-detail-panel">
          <div className="story-hero">
            <div>
              <div className="section-label">
                EVIDENCE ANSWER PATH
              </div>

              <h3>
                What did the search find?
              </h3>

              <p>
                “{searchResult.query}”
              </p>
            </div>

            <span className="status-badge status-ready">
              {searchResult.results.length}
              {" "}
              result
              {searchResult.results.length === 1
                ? ""
                : "s"}
            </span>
          </div>

          <div className="story-metrics">
            <div>
              <span>Retrieval</span>
              <strong>
                {humanize(
                  searchResult.mode,
                )}
              </strong>
            </div>

            <div>
              <span>Top K</span>
              <strong>
                {searchResult.top_k}
              </strong>
            </div>

            <div>
              <span>Model</span>
              <strong>
                {searchResult.embedding_model}
              </strong>
            </div>

            <div>
              <span>Case</span>
              <strong>
                {caseRecord.case_number}
              </strong>
            </div>
          </div>

          {searchResult.results.length === 0 && (
            <div
              className="empty-state"
              style={{
                marginTop: "18px",
              }}
            >
              No matching evidence was found.
            </div>
          )}

          {searchResult.results.map(
            (result, index) => {
              const sourceDocument =
                documents.find(
                  (document) =>
                    document.id ===
                    result.document_id,
                )

              const metadataFilename =
                result.metadata_json[
                  "document_filename"
                ]

              const filename =
                typeof metadataFilename ===
                "string"
                  ? metadataFilename
                  : sourceDocument?.filename ??
                    result.document_id

              return (
                <article
                  className="chunk-card"
                  key={result.chunk_id}
                >
                  <div className="chunk-card-header">
                    <strong>
                      Result #{index + 1}
                    </strong>

                    <span>
                      {filename}
                      {" | "}
                      Chunk #{result.chunk_index}
                    </span>
                  </div>

                  <div
                    className="document-metadata"
                    style={{
                      margin: "14px",
                    }}
                  >
                    <div>
                      <span>
                        Vector Similarity
                      </span>

                      <strong>
                        {formatSimilarity(
                          result.vector_similarity,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Hybrid Score
                      </span>

                      <strong>
                        {formatScore(
                          result.hybrid_score,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Vector Rank
                      </span>

                      <strong>
                        {result.vector_rank ??
                          "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Keyword Rank
                      </span>

                      <strong>
                        {result.keyword_rank ??
                          "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Keyword Score
                      </span>

                      <strong>
                        {formatScore(
                          result.keyword_score,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Document
                      </span>

                      <strong>
                        {filename}
                      </strong>
                    </div>
                  </div>

                  <pre>
                    {result.content}
                  </pre>

                  {sourceDocument && (
                    <div
                      style={{
                        padding:
                          "0 14px 14px",
                      }}
                    >
                      <button
                        className="secondary-action-button"
                        type="button"
                        onClick={() =>
                          selectSearchDocument(
                            result.document_id,
                          )
                        }
                      >
                        Open Source Document
                      </button>
                    </div>
                  )}
                </article>
              )
            },
          )}
        </section>
      )}

      {error && (
        <div className="error-panel">
          {error}
        </div>
      )}

      {loadingDocuments && (
        <div className="empty-state">
          Loading evidence...
        </div>
      )}

      {!loadingDocuments &&
        documents.length === 0 && (
          <div className="empty-state">
            No evidence documents available.
          </div>
        )}

      {!loadingDocuments &&
        documents.length > 0 && (
          <div className="evidence-layout">
            <aside className="documents-panel">
              <div className="section-label">
                DOCUMENTS
              </div>

              <div className="document-list">
                {documents.map(
                  (document) => (
                    <button
                      key={document.id}
                      type="button"
                      className={
                        selectedDocument?.id ===
                        document.id
                          ? "document-item active"
                          : "document-item"
                      }
                      onClick={() => {
                        setChunks([])

                        setSelectedDocument(
                          document,
                        )
                      }}
                    >
                      <strong>
                        {document.filename}
                      </strong>

                      <span>
                        {document.ingestion_status}
                        {" | "}
                        {formatBytes(
                          document.size_bytes,
                        )}
                      </span>
                    </button>
                  ),
                )}
              </div>
            </aside>

            <div className="document-detail-panel">
              {selectedDocument && (
                <>
                  <div className="story-hero">
                    <div>
                      <div className="section-label">
                        EVIDENCE STORY
                      </div>

                      <h3>
                        {selectedDocument.filename}
                      </h3>

                      <p>
                        {evidenceStage(
                          selectedDocument,
                        )}
                      </p>
                    </div>

                    <span
                      className={
                        `status-badge status-${selectedDocument.ingestion_status}`
                      }
                    >
                      {humanize(
                        selectedDocument.ingestion_status,
                      )}
                    </span>
                  </div>

                  <section className="story-timeline evidence-story-timeline">
                    <div className="story-timeline-item done">
                      <span>1</span>
                      <strong>Received</strong>
                      <small>
                        Evidence attached to the case
                      </small>
                    </div>

                    <div
                      className={
                        selectedDocument.parser_name
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>2</span>
                      <strong>Parsed</strong>
                      <small>
                        Text extracted and structured
                      </small>
                    </div>

                    <div
                      className={
                        chunks.length > 0
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>3</span>
                      <strong>Chunked</strong>
                      <small>
                        Evidence split into retrievable units
                      </small>
                    </div>

                    <div
                      className={
                        selectedDocument.ingestion_status === "ready" ||
                        selectedDocument.ingestion_status === "embedded"
                          ? "story-timeline-item done"
                          : "story-timeline-item"
                      }
                    >
                      <span>4</span>
                      <strong>Ready</strong>
                      <small>
                        Available to Hybrid RAG
                      </small>
                    </div>
                  </section>

                  <div className="document-metadata">
                    <div>
                      <span>
                        Content Type
                      </span>

                      <strong>
                        {selectedDocument.content_type ??
                          "Unknown"}
                      </strong>
                    </div>

                    <div>
                      <span>Source</span>

                      <strong>
                        {selectedDocument.source_type}
                      </strong>
                    </div>

                    <div>
                      <span>Parser</span>

                      <strong>
                        {selectedDocument.parser_name ??
                          "Not parsed"}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Text Length
                      </span>

                      <strong>
                        {selectedDocument.text_length ??
                          "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span>Size</span>

                      <strong>
                        {formatBytes(
                          selectedDocument.size_bytes,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>Chunks</span>

                      <strong>
                        {chunks.length}
                      </strong>
                    </div>
                  </div>

                  {selectedDocument.ingestion_error && (
                    <div className="error-panel">
                      {selectedDocument.ingestion_error}
                    </div>
                  )}

                  <div className="chunks-header">
                    <div>
                      <div className="section-label">
                        PARSED EVIDENCE
                      </div>

                      <h3>
                        What CaseMesh can retrieve
                      </h3>
                    </div>
                  </div>

                  {loadingChunks && (
                    <div className="empty-state">
                      Loading chunks...
                    </div>
                  )}

                  {!loadingChunks &&
                    chunks.length === 0 && (
                      <div className="empty-state">
                        No parsed chunks available.
                      </div>
                    )}

                  {!loadingChunks &&
                    chunks.map(
                      (chunk, index) => (
                        <article
                          className="evidence-excerpt-card"
                          key={chunk.id}
                        >
                          <div className="evidence-excerpt-heading">
                            <div>
                              <span>
                                Evidence excerpt
                              </span>

                              <strong>
                                Source passage
                                {" "}
                                {index + 1}
                              </strong>
                            </div>

                            <span className="story-pill story-tone-good">
                              Readable
                            </span>
                          </div>

                          <p>
                            {chunk.content}
                          </p>

                          <details className="evidence-technical-details">
                            <summary>
                              Technical details
                            </summary>

                            <div className="evidence-technical-grid">
                              <div>
                                <span>Chunk</span>
                                <strong>
                                  #{chunk.chunk_index}
                                </strong>
                              </div>

                              <div>
                                <span>Characters</span>
                                <strong>
                                  {chunk.char_count}
                                </strong>
                              </div>

                              <div>
                                <span>Chunk ID</span>
                                <strong>
                                  {chunk.id}
                                </strong>
                              </div>
                            </div>
                          </details>
                        </article>
                      ),
                    )}
                </>
              )}
            </div>
          </div>
        )}
    </section>
  )
}


export default EvidenceWorkspace
