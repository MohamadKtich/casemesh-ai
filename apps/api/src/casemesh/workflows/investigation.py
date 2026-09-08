from typing import Any, Literal, cast

from langgraph.graph import END, START, StateGraph

from casemesh.core.config import Settings
from casemesh.db.models import InvestigationRun
from casemesh.services.case_reader import CaseReader
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.schemas.answers import EvidenceCitation
from casemesh.schemas.retrieval import RetrievalResult
from casemesh.services.answers import AnswerService
from casemesh.services.retrieval_contract import RetrievalSearcher
from casemesh.workflows.state import InvestigationState

RouteDecision = Literal[
    "retry_retrieval",
    "identify_gaps",
    "produce_findings",
]


def choose_next_step(state: InvestigationState) -> RouteDecision:
    confidence = state.get("assessment_confidence")
    abstained = state.get("assessment_abstained", False)
    attempt = state.get("attempt", 0)
    max_retries = state.get("max_retries", 0)

    insufficient = abstained or confidence == "low"

    if insufficient and attempt < max_retries:
        return "retry_retrieval"

    if insufficient:
        return "identify_gaps"

    return "produce_findings"


class InvestigationWorkflow:
    def __init__(
        self,
        *,
        run: InvestigationRun,
        settings: Settings,
        case_reader: CaseReader,
        investigation_repository: InvestigationRepository,
        retrieval_service: RetrievalSearcher,
        answer_service: AnswerService,
    ) -> None:
        self._run = run
        self._settings = settings
        self._cases = case_reader
        self._investigations = investigation_repository
        self._retrieval = retrieval_service
        self._answers = answer_service
        self._graph: Any = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(InvestigationState)

        graph.add_node("initialize", self._initialize)
        graph.add_node("analyze_case", self._analyze_case)
        graph.add_node("plan_investigation", self._plan_investigation)
        graph.add_node("retrieve_evidence", self._retrieve_evidence)
        graph.add_node("assess_evidence", self._assess_evidence)
        graph.add_node("retry_retrieval", self._retry_retrieval)
        graph.add_node("identify_gaps", self._identify_gaps)
        graph.add_node("produce_findings", self._produce_findings)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "analyze_case")
        graph.add_edge("analyze_case", "plan_investigation")
        graph.add_edge("plan_investigation", "retrieve_evidence")
        graph.add_edge("retrieve_evidence", "assess_evidence")

        graph.add_conditional_edges(
            "assess_evidence",
            choose_next_step,
            {
                "retry_retrieval": "retry_retrieval",
                "identify_gaps": "identify_gaps",
                "produce_findings": "produce_findings",
            },
        )

        graph.add_edge("retry_retrieval", "retrieve_evidence")
        graph.add_edge("identify_gaps", "produce_findings")
        graph.add_edge("produce_findings", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile()

    async def run(
        self,
        initial_state: InvestigationState,
    ) -> InvestigationState:
        result = await self._graph.ainvoke(initial_state)
        return cast(InvestigationState, result)

    async def _initialize(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        await self._investigations.mark_running(
            self._run,
            current_step="initialize",
        )
        return {
            "status": "running",
            "current_step": "initialize",
            "attempt": state.get("attempt", 0),
            "max_retries": state.get(
                "max_retries",
                self._settings.workflow_max_retries,
            ),
            "search_query": state["objective"],
        }

    async def _analyze_case(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        self._run.current_step = "analyze_case"

        case = await self._cases.get(state["case_id"])
        if case is None:
            raise RuntimeError("Case disappeared while the workflow was running.")

        analysis = (
            f"Case {case.case_number}: {case.title}. "
            f"Current status: {case.status}. Priority: {case.priority}. "
            f"Investigation objective: {state['objective']}"
        )

        self._run.analysis_text = analysis
        await self._investigations.save(self._run)

        return {
            "current_step": "analyze_case",
            "case_analysis": analysis,
        }

    async def _plan_investigation(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        plan = [
            {"step": 1, "title": "Establish verified case facts and timeline."},
            {"step": 2, "title": "Retrieve evidence relevant to the objective."},
            {"step": 3, "title": "Assess evidence sufficiency and grounding."},
            {"step": 4, "title": "Identify material evidence gaps if present."},
            {
                "step": 5,
                "title": "Produce a cited finding without external actions.",
            },
        ]

        self._run.current_step = "plan_investigation"
        self._run.plan_json = plan
        await self._investigations.save(self._run)

        return {
            "current_step": "plan_investigation",
            "plan": plan,
        }

    async def _retrieve_evidence(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        query = state.get("search_query", state["objective"])

        result = await self._retrieval.search(
            case_id=state["case_id"],
            query=query,
            top_k=self._settings.workflow_retrieval_top_k,
        )

        evidence = [self._evidence_dict(item) for item in result.results]

        self._run.current_step = "retrieve_evidence"
        self._run.evidence_json = evidence
        self._run.attempt = state.get("attempt", 0)
        await self._investigations.save(self._run)

        return {
            "current_step": "retrieve_evidence",
            "evidence": evidence,
        }

    async def _assess_evidence(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        question = (
            "Determine whether the available case evidence supports a "
            "defensible finding for this investigation objective: "
            f"{state['objective']} "
            "Explain only what the evidence establishes and cite it."
        )

        answer = await self._answers.answer(
            case_id=state["case_id"],
            question=question,
            top_k=self._settings.workflow_retrieval_top_k,
        )

        citations = [self._citation_dict(citation) for citation in answer.citations]

        self._run.current_step = "assess_evidence"
        self._run.assessment_text = answer.answer
        self._run.confidence = answer.confidence
        self._run.abstained = answer.abstained
        self._run.citations_json = citations
        await self._investigations.save(self._run)

        return {
            "current_step": "assess_evidence",
            "assessment": answer.answer,
            "assessment_confidence": answer.confidence,
            "assessment_abstained": answer.abstained,
            "citations": citations,
        }

    async def _retry_retrieval(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        next_attempt = state.get("attempt", 0) + 1
        expanded_query = (
            f"{state['objective']} "
            "incident timeline service impact policy SLA customer request "
            "verified operational evidence mitigation root cause"
        )

        self._run.current_step = "retry_retrieval"
        self._run.attempt = next_attempt
        await self._investigations.save(self._run)

        return {
            "current_step": "retry_retrieval",
            "attempt": next_attempt,
            "search_query": expanded_query,
        }

    async def _identify_gaps(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        gaps: list[dict[str, object]] = []

        if not state.get("evidence"):
            gaps.append(
                {
                    "code": "NO_RELEVANT_EVIDENCE",
                    "description": ("No relevant evidence was retrieved for the objective."),
                }
            )

        if state.get("assessment_abstained", False):
            gaps.append(
                {
                    "code": "INSUFFICIENT_SUPPORT",
                    "description": (
                        "The grounded assessment could not support a defensible conclusion."
                    ),
                }
            )

        if state.get("assessment_confidence") == "low":
            gaps.append(
                {
                    "code": "LOW_CONFIDENCE",
                    "description": ("Evidence confidence remained low after retrieval."),
                }
            )

        if state.get("attempt", 0) >= state.get("max_retries", 0):
            gaps.append(
                {
                    "code": "RETRY_BUDGET_EXHAUSTED",
                    "description": (
                        "The configured evidence retrieval retry budget was exhausted."
                    ),
                }
            )

        if not gaps:
            gaps.append(
                {
                    "code": "NO_MATERIAL_GAP_DETECTED",
                    "description": (
                        "No material evidence gap was detected by the current foundation workflow."
                    ),
                }
            )

        self._run.current_step = "identify_gaps"
        self._run.gaps_json = gaps
        await self._investigations.save(self._run)

        return {
            "current_step": "identify_gaps",
            "gaps": gaps,
        }

    async def _produce_findings(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        gap_context = self._format_gap_context(state.get("gaps", []))
        question = (
            "Produce a concise investigation finding for this objective: "
            f"{state['objective']} "
            "State only evidence-supported facts, cite the evidence, and "
            "explicitly acknowledge uncertainty or missing information. "
            f"Known workflow gaps: {gap_context}"
        )

        answer = await self._answers.answer(
            case_id=state["case_id"],
            question=question,
            top_k=self._settings.workflow_retrieval_top_k,
        )

        citations = [self._citation_dict(citation) for citation in answer.citations]

        self._run.current_step = "produce_findings"
        self._run.findings_text = answer.answer
        self._run.confidence = answer.confidence
        self._run.abstained = answer.abstained
        self._run.citations_json = citations
        await self._investigations.save(self._run)

        return {
            "current_step": "produce_findings",
            "findings": answer.answer,
            "findings_confidence": answer.confidence,
            "findings_abstained": answer.abstained,
            "citations": citations,
        }

    async def _finalize(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        if "findings_confidence" in state:
            self._run.confidence = state["findings_confidence"]

        if "findings_abstained" in state:
            self._run.abstained = state["findings_abstained"]

        await self._investigations.mark_completed(self._run)

        return {
            "status": "completed",
            "current_step": "completed",
        }

    def _evidence_dict(
        self,
        result: RetrievalResult,
    ) -> dict[str, object]:
        excerpt = result.content
        limit = self._settings.workflow_evidence_excerpt_chars
        if len(excerpt) > limit:
            excerpt = excerpt[: max(0, limit - 3)].rstrip() + "..."

        return {
            "chunk_id": str(result.chunk_id),
            "document_id": str(result.document_id),
            "chunk_index": result.chunk_index,
            "hybrid_score": result.hybrid_score,
            "vector_rank": result.vector_rank,
            "keyword_rank": result.keyword_rank,
            "excerpt": excerpt,
        }

    @staticmethod
    def _citation_dict(
        citation: EvidenceCitation,
    ) -> dict[str, object]:
        return {
            "label": citation.label,
            "chunk_id": str(citation.chunk_id),
            "document_id": str(citation.document_id),
            "chunk_index": citation.chunk_index,
            "excerpt": citation.excerpt,
        }

    @staticmethod
    def _format_gap_context(
        gaps: list[dict[str, object]],
    ) -> str:
        if not gaps:
            return "none identified"

        descriptions = [str(gap.get("description", "unspecified gap")) for gap in gaps]
        return "; ".join(descriptions)
