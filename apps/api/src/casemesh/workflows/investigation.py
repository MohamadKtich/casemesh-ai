from collections.abc import Mapping
from typing import Any, Literal, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from casemesh.alerts import (
    AlertDispatcher,
    AlertDispatchResult,
    AlertEvent,
    AlertSeverity,
)
from casemesh.core.config import Settings
from casemesh.db.models import InvestigationRun
from casemesh.intelligence.contracts import (
    ReviewEvidence,
    SecondReviewProvider,
    SecondReviewRequest,
)
from casemesh.intelligence.guarded_review import (
    SecondReviewGuardrailBlockedError,
    SecondReviewGuardrailFailureError,
)
from casemesh.intelligence.risk_triggers import (
    RiskTriggerContext,
    RiskTriggerEngine,
)
from casemesh.intelligence.second_review_gate import (
    evaluate_second_review,
)
from casemesh.repositories.investigations import InvestigationRepository
from casemesh.schemas.answers import EvidenceCitation
from casemesh.schemas.retrieval import RetrievalResult
from casemesh.services.answers import AnswerService
from casemesh.services.case_reader import CaseReader
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


PostFindingsRoute = Literal[
    "second_review",
    "finalize",
]


def choose_post_findings_step(
    state: InvestigationState,
) -> PostFindingsRoute:
    """Route to optional second review without deciding why it was requested."""

    if state.get(
        "second_review_requested",
        False,
    ):
        return "second_review"

    return "finalize"


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
        second_review_provider: SecondReviewProvider | None = None,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self._run = run
        self._settings = settings
        self._cases = case_reader
        self._investigations = investigation_repository
        self._retrieval = retrieval_service
        self._answers = answer_service
        self._second_review_provider = second_review_provider
        self._alerts = alert_dispatcher if alert_dispatcher is not None else AlertDispatcher(None)
        self._risk_trigger_engine = RiskTriggerEngine()
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
        graph.add_node(
            "evaluate_risk_triggers",
            self._evaluate_risk_triggers,
        )
        graph.add_node("second_review", self._second_review)
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

        graph.add_edge(
            "produce_findings",
            "evaluate_risk_triggers",
        )

        graph.add_conditional_edges(
            "evaluate_risk_triggers",
            choose_post_findings_step,
            {
                "second_review": "second_review",
                "finalize": "finalize",
            },
        )

        graph.add_edge("second_review", "finalize")
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

    async def _evaluate_risk_triggers(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        """Evaluate deterministic signals before optional second review."""

        gap_codes = self._gap_codes(
            state.get(
                "gaps",
                [],
            )
        )

        decision = self._risk_trigger_engine.evaluate(
            RiskTriggerContext(
                findings_confidence=state.get("findings_confidence"),
                findings_abstained=state.get(
                    "findings_abstained",
                    False,
                ),
                gap_codes=gap_codes,
                security_flags=tuple(
                    state.get(
                        "security_flags",
                        [],
                    )
                ),
                evidence_conflict=state.get(
                    "evidence_conflict",
                    False,
                ),
                prompt_injection_signal=state.get(
                    "prompt_injection_signal",
                    False,
                ),
                manual_second_review_requested=state.get(
                    "manual_second_review_requested",
                    False,
                ),
            )
        )

        trigger_codes = [str(code) for code in decision.reason_codes]

        trigger_metadata: dict[str, object] = {
            "request_second_review": (decision.request_second_review),
            "reason_codes": trigger_codes,
            "triggers": [
                {
                    "code": trigger.code,
                    "source": trigger.source,
                    "rationale": trigger.rationale,
                }
                for trigger in decision.triggers
            ],
        }

        self._run.current_step = "evaluate_risk_triggers"

        metadata = dict(self._run.metadata_json or {})

        metadata["risk_triggers"] = trigger_metadata

        self._run.metadata_json = metadata

        await self._investigations.save(self._run)

        return {
            "current_step": "evaluate_risk_triggers",
            "risk_trigger_codes": trigger_codes,
            "risk_triggers": trigger_metadata,
            "second_review_requested": (decision.request_second_review),
        }

    def _existing_second_review_outcome(
        self,
    ) -> dict[str, object] | None:
        metadata = dict(self._run.metadata_json or {})

        raw_outcome = metadata.get("second_review")

        if not isinstance(
            raw_outcome,
            dict,
        ):
            return None

        raw_status = raw_outcome.get("status")

        if (
            not isinstance(
                raw_status,
                str,
            )
            or not raw_status.strip()
        ):
            return None

        return {
            str(key): value
            for key, value in raw_outcome.items()
            if isinstance(
                key,
                str,
            )
        }

    @staticmethod
    def _reserved_second_review_attempts(
        metadata: dict[str, object],
    ) -> int:
        raw_budget = metadata.get("second_review_budget")

        if not isinstance(
            raw_budget,
            dict,
        ):
            return 0

        raw_attempts = raw_budget.get("reserved_attempts")

        if (
            isinstance(
                raw_attempts,
                int,
            )
            and not isinstance(
                raw_attempts,
                bool,
            )
            and raw_attempts >= 0
        ):
            return raw_attempts

        return 0

    async def _reserve_second_review_attempt(
        self,
    ) -> tuple[
        bool,
        int,
    ]:
        metadata = dict(self._run.metadata_json or {})

        reserved_attempts = self._reserved_second_review_attempts(metadata)

        max_reviews = self._settings.aws_max_reviews_per_investigation

        if reserved_attempts >= max_reviews:
            metadata["second_review_budget"] = {
                "reserved_attempts": (reserved_attempts),
                "max_reviews": (max_reviews),
            }

            self._run.metadata_json = metadata

            return (
                False,
                reserved_attempts,
            )

        next_attempt = reserved_attempts + 1

        metadata["second_review_budget"] = {
            "reserved_attempts": (next_attempt),
            "max_reviews": (max_reviews),
        }

        self._run.metadata_json = metadata

        # Persist before the external provider call.
        # If this save fails, the provider must not run.
        await self._investigations.save(self._run)

        return (
            True,
            next_attempt,
        )

    def _is_real_aws_second_review_provider(
        self,
        provider: SecondReviewProvider,
    ) -> bool:
        """Identify the configured real Bedrock SDK review boundary."""
        return (
            self._settings.aws_client_mode == "sdk"
            and self._settings.aws_bedrock_review_enabled
            and provider.provider_name == "aws-bedrock"
        )

    async def _second_review(
        self,
        state: InvestigationState,
    ) -> InvestigationState:
        """Run one replay-safe advisory second review.

        Existing terminal outcomes are reused without a new provider or alert
        call. External review attempts are reserved durably before invocation.
        Exhausted budgets fail closed to human review.
        """

        existing_outcome = self._existing_second_review_outcome()

        if existing_outcome is not None:
            return {
                "current_step": "second_review",
                "second_review": (existing_outcome),
            }

        provider = self._second_review_provider

        if provider is None:
            outcome: dict[
                str,
                object,
            ] = {
                "status": "unavailable",
                "effective_route": ("human_review"),
                "forced_human_review": True,
                "reason_codes": [
                    "provider_unavailable",
                ],
            }

        else:
            try:
                request = self._build_second_review_request(state)
            except Exception as exc:
                # Local request-validation failures do not consume
                # an external-review attempt.
                outcome = {
                    "status": "failed",
                    "provider": (provider.provider_name),
                    "model": (provider.model_name),
                    "effective_route": ("human_review"),
                    "forced_human_review": True,
                    "reason_codes": [
                        "provider_failure",
                    ],
                    "error_type": (type(exc).__name__),
                }

            else:
                (
                    attempt_reserved,
                    reserved_attempts,
                ) = await self._reserve_second_review_attempt()

                if not attempt_reserved:
                    outcome = {
                        "status": ("budget_exhausted"),
                        "effective_route": ("human_review"),
                        "forced_human_review": True,
                        "reason_codes": [
                            "review_budget_exhausted",
                        ],
                        "reserved_attempts": (reserved_attempts),
                        "max_reviews": (self._settings.aws_max_reviews_per_investigation),
                    }

                else:
                    try:
                        result = await provider.review(request)

                        decision = evaluate_second_review(result)

                        outcome = {
                            "status": "completed",
                            "provider": (result.provider),
                            "model": result.model,
                            "agreement": (result.agreement),
                            "risk_level": (result.risk_level),
                            "concerns": list(result.concerns),
                            "provider_route": (result.recommended_route),
                            "effective_route": (decision.effective_route),
                            "forced_human_review": (decision.forced_human_review),
                            "reason_codes": list(decision.reason_codes),
                            "rationale": (result.rationale),
                        }

                    except SecondReviewGuardrailBlockedError as exc:
                        reason_codes = ["guardrail_blocked"]

                        for reason_code in exc.assessment.reason_codes:
                            if reason_code not in reason_codes:
                                reason_codes.append(reason_code)

                        outcome = {
                            "status": ("guardrail_blocked"),
                            "guardrail_stage": (exc.stage),
                            "guardrail_provider": (exc.assessment.provider),
                            "effective_route": ("human_review"),
                            "forced_human_review": True,
                            "reason_codes": (reason_codes),
                        }

                    except SecondReviewGuardrailFailureError as exc:
                        outcome = {
                            "status": ("guardrail_failed"),
                            "guardrail_stage": (exc.stage),
                            "effective_route": ("human_review"),
                            "forced_human_review": True,
                            "reason_codes": [
                                "guardrail_failure",
                            ],
                            "error_type": (exc.error_type),
                        }

                        if (
                            self._is_real_aws_second_review_provider(provider)
                            and self._settings.aws_bedrock_guardrails_enabled
                        ):
                            outcome["aws_boundary_failure"] = True
                            outcome["aws_boundary_component"] = "bedrock_guardrails"

                    except Exception as exc:
                        outcome = {
                            "status": "failed",
                            "provider": (provider.provider_name),
                            "model": (provider.model_name),
                            "effective_route": ("human_review"),
                            "forced_human_review": True,
                            "reason_codes": [
                                "provider_failure",
                            ],
                            "error_type": (type(exc).__name__),
                        }

                        if self._is_real_aws_second_review_provider(provider):
                            outcome["aws_boundary_failure"] = True
                            outcome["aws_boundary_component"] = "bedrock_review"

        alert_event = self._second_review_alert_event(
            state=state,
            outcome=outcome,
        )

        if alert_event is not None:
            alert_result = await self._alerts.dispatch(alert_event)

            outcome["alert_delivery"] = self._alert_delivery_metadata(alert_result)

        self._run.current_step = "second_review"

        metadata = dict(self._run.metadata_json or {})

        metadata["second_review"] = outcome

        self._run.metadata_json = metadata

        await self._investigations.save(self._run)

        return {
            "current_step": ("second_review"),
            "second_review": outcome,
        }

    def _second_review_alert_event(
        self,
        *,
        state: InvestigationState,
        outcome: dict[str, object],
    ) -> AlertEvent | None:
        raw_status = outcome.get("status")

        status = (
            raw_status.strip()
            if isinstance(
                raw_status,
                str,
            )
            and raw_status.strip()
            else None
        )

        raw_reason_codes = outcome.get(
            "reason_codes",
            [],
        )

        reason_codes: tuple[
            str,
            ...,
        ] = ()

        if isinstance(
            raw_reason_codes,
            (
                list,
                tuple,
            ),
        ):
            reason_codes = tuple(
                value.strip()
                for value in raw_reason_codes
                if isinstance(
                    value,
                    str,
                )
                and value.strip()
            )

        raw_risk_level = outcome.get("risk_level")

        risk_level = (
            raw_risk_level.strip()
            if isinstance(
                raw_risk_level,
                str,
            )
            and raw_risk_level.strip()
            else None
        )

        if status == "completed" and "review_disagreed" in reason_codes:
            severity: AlertSeverity = "critical" if risk_level == "critical" else "high"

            return AlertEvent(
                event_type=("SECOND_REVIEW_DISAGREEMENT"),
                severity=severity,
                source="second_review",
                case_id=state["case_id"],
                investigation_run_id=(self._run.id),
                reason_codes=(reason_codes),
                risk_level=risk_level,
                status=status,
            )

        if status == "guardrail_blocked":
            return AlertEvent(
                event_type=("GUARDRAIL_BLOCK"),
                severity="critical",
                source="guardrail",
                case_id=state["case_id"],
                investigation_run_id=(self._run.id),
                reason_codes=(reason_codes),
                status=status,
            )

        if outcome.get("aws_boundary_failure") is True and status in {
            "failed",
            "guardrail_failed",
        }:
            boundary_reason_codes = ["aws_boundary_failure"]

            for reason_code in reason_codes:
                if reason_code not in boundary_reason_codes:
                    boundary_reason_codes.append(reason_code)

            return AlertEvent(
                event_type=("CROSS_CLOUD_FAILURE"),
                severity="high",
                source="aws_boundary",
                case_id=state["case_id"],
                investigation_run_id=(self._run.id),
                reason_codes=tuple(boundary_reason_codes),
                status=status,
            )

        return None

    @staticmethod
    def _alert_delivery_metadata(
        result: AlertDispatchResult,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "event_type": result.event_type,
            "status": result.status,
            "attempted": result.attempted,
            "delivered": result.delivered,
        }

        if result.provider is not None:
            metadata["provider"] = result.provider

        if result.message_id is not None:
            metadata["message_id"] = result.message_id

        if result.error_type is not None:
            metadata["error_type"] = result.error_type

        return metadata

    def _build_second_review_request(
        self,
        state: InvestigationState,
    ) -> SecondReviewRequest:
        finding = state.get("findings")

        if (
            not isinstance(
                finding,
                str,
            )
            or not finding.strip()
        ):
            raise ValueError("Second review requires a non-blank primary finding.")

        return SecondReviewRequest(
            case_id=state["case_id"],
            investigation_run_id=self._run.id,
            objective=state["objective"],
            primary_finding=finding,
            primary_confidence=state.get("findings_confidence"),
            primary_abstained=state.get(
                "findings_abstained",
                False,
            ),
            evidence=self._review_evidence(
                state.get(
                    "citations",
                    [],
                )
            ),
            gap_codes=self._gap_codes(
                state.get(
                    "gaps",
                    [],
                )
            ),
        )

    @staticmethod
    def _review_evidence(
        citations: list[dict[str, object]],
    ) -> tuple[ReviewEvidence, ...]:
        evidence: list[ReviewEvidence] = []

        for raw_citation in citations:
            if not isinstance(
                raw_citation,
                Mapping,
            ):
                raise ValueError("Second-review citation must be a mapping.")

            raw_chunk_id = raw_citation.get("chunk_id")
            raw_document_id = raw_citation.get("document_id")
            raw_chunk_index = raw_citation.get("chunk_index")
            raw_excerpt = raw_citation.get("excerpt")
            raw_label = raw_citation.get("label")

            if not isinstance(
                raw_chunk_index,
                int,
            ) or isinstance(
                raw_chunk_index,
                bool,
            ):
                raise ValueError("Second-review citation chunk_index must be an integer.")

            if not isinstance(
                raw_excerpt,
                str,
            ):
                raise ValueError("Second-review citation excerpt must be a string.")

            citation_label = (
                raw_label.strip()
                if isinstance(
                    raw_label,
                    str,
                )
                and raw_label.strip()
                else None
            )

            evidence.append(
                ReviewEvidence(
                    chunk_id=UUID(str(raw_chunk_id)),
                    document_id=UUID(str(raw_document_id)),
                    chunk_index=raw_chunk_index,
                    excerpt=raw_excerpt,
                    citation_label=citation_label,
                )
            )

        return tuple(evidence)

    @staticmethod
    def _gap_codes(
        gaps: list[dict[str, object]],
    ) -> tuple[str, ...]:
        codes: list[str] = []

        for raw_gap in gaps:
            if not isinstance(
                raw_gap,
                Mapping,
            ):
                continue

            raw_code = raw_gap.get("code")

            if not isinstance(
                raw_code,
                str,
            ):
                continue

            code = raw_code.strip()

            if code and code not in codes:
                codes.append(code)

        return tuple(codes)

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
