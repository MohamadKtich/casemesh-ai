import json
import re
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from casemesh.grounding.context import EvidenceContextBuilder, EvidenceSource
from casemesh.llm.base import GenerationProvider
from casemesh.schemas.answers import (
    EvidenceCitation,
    GroundedAnswerResponse,
    GroundedModelOutput,
    GroundingMetadata,
)
from casemesh.services.retrieval import RetrievalService

_CITATION_RE = re.compile(r"\[(E\d+)\]")


def extract_citation_labels(answer: str) -> list[str]:
    seen: set[str] = set()
    labels: list[str] = []

    for label in _CITATION_RE.findall(answer):
        if label not in seen:
            seen.add(label)
            labels.append(label)

    return labels


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")

    return text[start : end + 1]


class AnswerService:
    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        generation_provider: GenerationProvider,
        context_builder: EvidenceContextBuilder,
    ) -> None:
        self._retrieval = retrieval_service
        self._generation = generation_provider
        self._context_builder = context_builder

    async def generation_health(self) -> dict[str, object]:
        return await self._generation.health()

    async def answer(
        self,
        *,
        case_id: UUID,
        question: str,
        top_k: int,
    ) -> GroundedAnswerResponse:
        retrieval = await self._retrieval.search(
            case_id=case_id,
            query=question,
            top_k=top_k,
        )

        sources = self._context_builder.build(retrieval.results)

        if not sources:
            return GroundedAnswerResponse(
                question=question,
                answer=("I cannot answer this from the currently available case evidence."),
                confidence="low",
                abstained=True,
                citations=[],
                grounding=GroundingMetadata(
                    retrieved_chunks=len(retrieval.results),
                    context_chunks=0,
                    cited_chunks=0,
                    citation_source_ratio=0.0,
                ),
                retrieval_mode=retrieval.mode,
                embedding_model=retrieval.embedding_model,
                generation_provider=self._generation.provider_name,
                generation_model=self._generation.model_name,
            )

        output = await self._generate_validated(
            question=question,
            sources=sources,
        )

        source_by_label = {source.label: source for source in sources}
        labels = extract_citation_labels(output.answer)
        valid_labels = [label for label in labels if label in source_by_label]

        citations = [self._citation_from_source(source_by_label[label]) for label in valid_labels]

        ratio = len(citations) / len(sources) if sources else 0.0

        return GroundedAnswerResponse(
            question=question,
            answer=output.answer,
            confidence=output.confidence,
            abstained=output.abstained,
            citations=citations,
            grounding=GroundingMetadata(
                retrieved_chunks=len(retrieval.results),
                context_chunks=len(sources),
                cited_chunks=len(citations),
                citation_source_ratio=round(ratio, 4),
            ),
            retrieval_mode=retrieval.mode,
            embedding_model=retrieval.embedding_model,
            generation_provider=self._generation.provider_name,
            generation_model=self._generation.model_name,
        )

    async def _generate_validated(
        self,
        *,
        question: str,
        sources: list[EvidenceSource],
    ) -> GroundedModelOutput:
        allowed_labels = [source.label for source in sources]
        evidence_context = self._context_builder.render(sources)

        system_prompt = (
            "You are CaseMesh, an evidence-grounded case analyst. "
            "Use only the evidence supplied by the user. "
            "Never use outside knowledge to fill factual gaps. "
            "Every factual sentence in a non-abstained answer must end "
            "with one or more evidence citations such as [E1]. "
            "Only use citation labels that appear in the supplied evidence. "
            "If the evidence is insufficient, clearly say that you cannot "
            "determine the answer, set abstained to true, and use confidence "
            "low. Return JSON only with exactly these keys: answer, "
            "confidence, abstained. confidence must be low, medium, or high."
        )

        user_prompt = (
            f"QUESTION:\n{question}\n\n"
            f"ALLOWED CITATIONS: {', '.join(allowed_labels)}\n\n"
            f"EVIDENCE:\n{evidence_context}"
        )

        last_error = "Unknown grounding validation failure."

        for attempt in range(2):
            if attempt == 1:
                user_prompt = (
                    "Repair the previous answer so it follows the grounding "
                    "contract exactly. Use only the evidence below. Every "
                    "factual sentence must contain one or more valid citation "
                    "labels. Return JSON only.\n\n"
                    f"QUESTION:\n{question}\n\n"
                    f"ALLOWED CITATIONS: {', '.join(allowed_labels)}\n\n"
                    f"EVIDENCE:\n{evidence_context}"
                )

            try:
                raw = await self._generation.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Generation provider is unavailable.",
                ) from exc
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc

            try:
                payload = json.loads(_extract_json_object(raw))
                output = GroundedModelOutput.model_validate(payload)
            except (
                json.JSONDecodeError,
                ValidationError,
                ValueError,
            ) as exc:
                last_error = f"Invalid structured model output: {exc}"
                continue

            labels = extract_citation_labels(output.answer)
            unknown = [label for label in labels if label not in allowed_labels]

            if unknown:
                last_error = "Model used unknown citation labels: " + ", ".join(unknown)
                continue

            if not output.abstained and not labels:
                last_error = "Non-abstained answer did not include evidence citations."
                continue

            return output

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=last_error,
        )

    @staticmethod
    def _citation_from_source(
        source: EvidenceSource,
    ) -> EvidenceCitation:
        excerpt = source.content
        if len(excerpt) > 320:
            excerpt = excerpt[:317].rstrip() + "..."

        return EvidenceCitation(
            label=source.label,
            chunk_id=source.chunk_id,
            document_id=source.document_id,
            chunk_index=source.chunk_index,
            excerpt=excerpt,
        )
