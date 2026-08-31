from typing import Any, Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from casemesh.workflows.approval_state import ActionApprovalState

PolicyRoute = Literal["blocked", "auto_approved", "human_review"]


def route_policy(state: ActionApprovalState) -> PolicyRoute:
    decision = state.get("policy_decision")

    if decision == "block":
        return "blocked"

    if decision == "allow":
        return "auto_approved"

    return "human_review"


class ActionApprovalWorkflow:
    def __init__(self, *, checkpointer: Any) -> None:
        self._graph: Any = self._build_graph(checkpointer)

    def _build_graph(self, checkpointer: Any) -> Any:
        graph = StateGraph(ActionApprovalState)

        graph.add_node("policy_gate", self._policy_gate)
        graph.add_node("blocked", self._blocked)
        graph.add_node("auto_approved", self._auto_approved)
        graph.add_node("human_review", self._human_review)
        graph.add_node("approved", self._approved)
        graph.add_node("rejected", self._rejected)

        graph.add_edge(START, "policy_gate")
        graph.add_conditional_edges(
            "policy_gate",
            route_policy,
            {
                "blocked": "blocked",
                "auto_approved": "auto_approved",
                "human_review": "human_review",
            },
        )
        graph.add_edge("blocked", END)
        graph.add_edge("auto_approved", END)
        graph.add_edge("approved", END)
        graph.add_edge("rejected", END)

        return graph.compile(checkpointer=checkpointer)

    async def start(
        self,
        state: ActionApprovalState,
    ) -> dict[str, object]:
        config = self._config(state["thread_id"])
        result = await self._graph.ainvoke(state, config=config)
        return cast(dict[str, object], result)

    async def resume(
        self,
        *,
        thread_id: str,
        decision: str,
        reviewer_ref: str,
        comment: str | None,
    ) -> dict[str, object]:
        config = self._config(thread_id)
        resume_payload: dict[str, object] = {
            "decision": decision,
            "reviewer_ref": reviewer_ref,
            "comment": comment or "",
        }
        result = await self._graph.ainvoke(
            Command(resume=resume_payload),
            config=config,
        )
        return cast(dict[str, object], result)

    @staticmethod
    def build_interrupt_payload(
        state: ActionApprovalState,
    ) -> dict[str, object]:
        return {
            "type": "human_approval_required",
            "question": state["interrupt_question"],
            "action_request_id": state["action_request_id"],
            "action_type": state["action_type"],
            "risk_level": state["risk_level"],
            "policy_rationale": state["policy_rationale"],
            "payload": state["payload"],
            "allowed_decisions": ["approve", "reject"],
            "execution_notice": (
                "Approval only authorizes a future execution step. "
                "Phase 26 does not execute external actions."
            ),
        }

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    @staticmethod
    def _policy_gate(
        state: ActionApprovalState,
    ) -> ActionApprovalState:
        return {
            "status": "policy_evaluated",
        }

    @staticmethod
    def _blocked(
        state: ActionApprovalState,
    ) -> ActionApprovalState:
        return {
            "status": "blocked",
        }

    @staticmethod
    def _auto_approved(
        state: ActionApprovalState,
    ) -> ActionApprovalState:
        return {
            "status": "auto_approved",
            "approval_decision": "auto_approved",
        }

    @staticmethod
    def _human_review(
        state: ActionApprovalState,
    ) -> Command[Literal["approved", "rejected"]]:
        response = interrupt(ActionApprovalWorkflow.build_interrupt_payload(state))
        review = cast(dict[str, object], response)

        decision = review.get("decision")
        reviewer_ref = review.get("reviewer_ref")
        comment = review.get("comment")

        update: ActionApprovalState = {
            "approval_decision": ("approved" if decision == "approve" else "rejected"),
            "reviewer_ref": (reviewer_ref if isinstance(reviewer_ref, str) else ""),
            "comment": comment if isinstance(comment, str) else "",
        }

        return Command(
            update=update,
            goto="approved" if decision == "approve" else "rejected",
        )

    @staticmethod
    def _approved(
        state: ActionApprovalState,
    ) -> ActionApprovalState:
        return {
            "status": "approved",
        }

    @staticmethod
    def _rejected(
        state: ActionApprovalState,
    ) -> ActionApprovalState:
        return {
            "status": "rejected",
        }
