import asyncio
import hashlib
from collections.abc import Mapping
from typing import Protocol, cast

from casemesh.core.config import Settings
from casemesh.integrations.aws.gateway import AWSIntelligenceGateway
from casemesh.intelligence.document_intelligence import (
    DocumentIntelligenceJob,
    DocumentIntelligenceProvider,
    DocumentIntelligenceRequest,
    DocumentIntelligenceResult,
    DocumentIntelligenceStatus,
    DocumentTextLine,
)


class TextractClientProtocol(Protocol):
    """Minimal Textract client surface required by CaseMesh."""

    def start_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        """Start asynchronous text extraction."""

    def get_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        """Read asynchronous text extraction results."""


class TextractPageLimitExceededError(RuntimeError):
    """Raised when a document exceeds the configured Textract page limit."""


class TextractPaginationLoopError(RuntimeError):
    """Raised when Textract repeats a pagination token."""


class TextractResponseParser:
    """Normalize Textract responses into CaseMesh document intelligence results."""

    provider_name = "aws-textract"

    def parse(
        self,
        *,
        job_id: str,
        response: Mapping[str, object],
    ) -> DocumentIntelligenceResult:
        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise ValueError("Textract job_id must not be blank.")

        raw_status = response.get("JobStatus")

        if not isinstance(raw_status, str):
            raise ValueError("Textract response is missing JobStatus.")

        status, warnings = self._normalize_status(raw_status)

        if status != "succeeded":
            return DocumentIntelligenceResult(
                provider=self.provider_name,
                job_id=normalized_job_id,
                status=status,
                text="",
                lines=(),
                page_count=self._page_count(response),
                warnings=warnings,
            )

        lines = self._lines(response)

        return DocumentIntelligenceResult(
            provider=self.provider_name,
            job_id=normalized_job_id,
            status=status,
            text="\n".join(line.text for line in lines),
            lines=lines,
            page_count=self._page_count(
                response,
                lines=lines,
            ),
            warnings=warnings,
        )

    @staticmethod
    def _normalize_status(
        raw_status: str,
    ) -> tuple[DocumentIntelligenceStatus, tuple[str, ...]]:
        status_map: dict[str, DocumentIntelligenceStatus] = {
            "IN_PROGRESS": "in_progress",
            "SUCCEEDED": "succeeded",
            "PARTIAL_SUCCESS": "succeeded",
            "FAILED": "failed",
        }

        if raw_status not in status_map:
            raise ValueError(f"Unsupported Textract JobStatus: {raw_status}")

        warnings: tuple[str, ...] = ()

        if raw_status == "PARTIAL_SUCCESS":
            warnings = ("PARTIAL_SUCCESS",)

        return status_map[raw_status], warnings

    @staticmethod
    def _lines(
        response: Mapping[str, object],
    ) -> tuple[DocumentTextLine, ...]:
        raw_blocks = response.get("Blocks")

        if raw_blocks is None:
            return ()

        if not isinstance(raw_blocks, list):
            raise ValueError("Textract response Blocks must be a list.")

        lines: list[DocumentTextLine] = []

        for raw_block in raw_blocks:
            if not isinstance(raw_block, Mapping):
                continue

            if raw_block.get("BlockType") != "LINE":
                continue

            raw_text = raw_block.get("Text")

            if not isinstance(raw_text, str):
                continue

            text = raw_text.strip()

            if not text:
                continue

            raw_page = raw_block.get("Page")

            page_number = (
                raw_page if isinstance(raw_page, int) and not isinstance(raw_page, bool) else 1
            )

            raw_confidence = raw_block.get("Confidence")

            confidence: float | None = None

            if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool):
                confidence = float(raw_confidence)

            lines.append(
                DocumentTextLine(
                    page_number=page_number,
                    text=text,
                    confidence=confidence,
                )
            )

        return tuple(lines)

    @staticmethod
    def _page_count(
        response: Mapping[str, object],
        *,
        lines: tuple[DocumentTextLine, ...] = (),
    ) -> int:
        raw_metadata = response.get("DocumentMetadata")

        if isinstance(raw_metadata, Mapping):
            raw_pages = raw_metadata.get("Pages")

            if isinstance(raw_pages, int) and not isinstance(raw_pages, bool) and raw_pages >= 0:
                return raw_pages

        if not lines:
            return 0

        return max(line.page_number for line in lines)


class MockTextractDocumentIntelligence:
    """Deterministic zero-network Textract stand-in."""

    provider_name = "aws-textract-mock"

    def __init__(
        self,
        *,
        extracted_text: str = "synthetic extracted document text",
        confidence: float = 99.0,
        fail_jobs: bool = False,
    ) -> None:
        normalized_text = extracted_text.strip()

        if not normalized_text:
            raise ValueError("Mock Textract extracted_text must not be blank.")

        if not 0 <= confidence <= 100:
            raise ValueError("Mock Textract confidence must be between 0 and 100.")

        self._extracted_text = normalized_text
        self._confidence = confidence
        self._fail_jobs = fail_jobs
        self._jobs: dict[str, DocumentIntelligenceRequest] = {}

    async def start(
        self,
        request: DocumentIntelligenceRequest,
    ) -> DocumentIntelligenceJob:
        seed = (
            f"{request.case_id}:"
            f"{request.investigation_run_id}:"
            f"{request.document_id}:"
            f"{request.staged.sha256}"
        )

        job_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()

        self._jobs[job_id] = request

        return DocumentIntelligenceJob(
            provider=self.provider_name,
            job_id=job_id,
            status="in_progress",
        )

    async def get(
        self,
        job_id: str,
    ) -> DocumentIntelligenceResult:
        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise ValueError("Mock Textract job_id must not be blank.")

        if normalized_job_id not in self._jobs:
            raise ValueError("Unknown mock Textract job_id.")

        if self._fail_jobs:
            return DocumentIntelligenceResult(
                provider=self.provider_name,
                job_id=normalized_job_id,
                status="failed",
                text="",
                lines=(),
                page_count=0,
                warnings=("SYNTHETIC_FAILURE",),
            )

        line = DocumentTextLine(
            page_number=1,
            text=self._extracted_text,
            confidence=self._confidence,
        )

        return DocumentIntelligenceResult(
            provider=self.provider_name,
            job_id=normalized_job_id,
            status="succeeded",
            text=self._extracted_text,
            lines=(line,),
            page_count=1,
        )

    async def health(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
            "job_count": len(self._jobs),
            "fail_jobs": self._fail_jobs,
        }


class TextractDocumentIntelligence:
    """Real asynchronous Textract document text-detection adapter."""

    provider_name = "aws-textract"
    max_results = 1000

    def __init__(
        self,
        *,
        client: TextractClientProtocol,
        max_pages: int = 20,
        expected_bucket: str | None = None,
        managed_prefix: str = "casemesh-temp/",
        notification_topic_arn: str | None = None,
        notification_role_arn: str | None = None,
    ) -> None:
        if max_pages <= 0:
            raise ValueError("Textract max_pages must be greater than zero.")

        normalized_expected_bucket: str | None = None

        if expected_bucket is not None:
            normalized_expected_bucket = expected_bucket.strip()

            if not normalized_expected_bucket:
                raise ValueError("Textract expected_bucket must not be blank.")

        normalized_prefix = managed_prefix.strip()

        if not normalized_prefix:
            raise ValueError("Textract managed_prefix must not be blank.")

        if not normalized_prefix.endswith("/"):
            raise ValueError("Textract managed_prefix must end with '/'.")

        prefix_body = normalized_prefix[:-1]

        if not prefix_body or any(part in {"", ".", ".."} for part in prefix_body.split("/")):
            raise ValueError("Textract managed_prefix contains an unsafe segment.")

        normalized_notification_topic_arn = (
            notification_topic_arn.strip() if notification_topic_arn is not None else None
        )

        normalized_notification_role_arn = (
            notification_role_arn.strip() if notification_role_arn is not None else None
        )

        if normalized_notification_topic_arn == "":
            raise ValueError("Textract notification_topic_arn must not be blank.")

        if normalized_notification_role_arn == "":
            raise ValueError("Textract notification_role_arn must not be blank.")

        if (normalized_notification_topic_arn is None) != (
            normalized_notification_role_arn is None
        ):
            raise ValueError("Textract notification topic and role must be configured together.")

        self._client = client
        self._parser = TextractResponseParser()
        self._max_pages = max_pages
        self._expected_bucket = normalized_expected_bucket
        self._managed_prefix = normalized_prefix
        self._notification_topic_arn = normalized_notification_topic_arn
        self._notification_role_arn = normalized_notification_role_arn

    async def start(
        self,
        request: DocumentIntelligenceRequest,
    ) -> DocumentIntelligenceJob:
        self._validate_staged_object(request)

        client_request_token = self._client_request_token(request)

        start_kwargs: dict[str, object] = {
            "DocumentLocation": {
                "S3Object": {
                    "Bucket": request.staged.bucket,
                    "Name": request.staged.object_key,
                }
            },
            "ClientRequestToken": client_request_token,
        }

        if self._notification_topic_arn is not None and self._notification_role_arn is not None:
            start_kwargs["NotificationChannel"] = {
                "SNSTopicArn": self._notification_topic_arn,
                "RoleArn": self._notification_role_arn,
            }

        raw_response = await asyncio.to_thread(
            self._client.start_document_text_detection,
            **start_kwargs,
        )

        response = self._require_mapping(
            raw_response,
            operation="StartDocumentTextDetection",
        )

        raw_job_id = response.get("JobId")

        if not isinstance(raw_job_id, str) or not raw_job_id.strip():
            raise ValueError("Textract StartDocumentTextDetection response is missing JobId.")

        return DocumentIntelligenceJob(
            provider=self.provider_name,
            job_id=raw_job_id.strip(),
            status="in_progress",
        )

    async def get(
        self,
        job_id: str,
    ) -> DocumentIntelligenceResult:
        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise ValueError("Textract job_id must not be blank.")

        first_response = await self._get_result_page(
            job_id=normalized_job_id,
            next_token=None,
        )

        raw_status = first_response.get("JobStatus")

        if raw_status not in {
            "SUCCEEDED",
            "PARTIAL_SUCCESS",
        }:
            return self._parser.parse(
                job_id=normalized_job_id,
                response=first_response,
            )

        self._enforce_page_limit(first_response)

        responses: list[Mapping[str, object]] = [
            first_response,
        ]

        seen_tokens: set[str] = set()

        next_token = self._next_token(first_response)

        while next_token is not None:
            if next_token in seen_tokens:
                raise TextractPaginationLoopError("Textract returned a repeated NextToken.")

            seen_tokens.add(next_token)

            response = await self._get_result_page(
                job_id=normalized_job_id,
                next_token=next_token,
            )

            raw_page_status = response.get("JobStatus")

            if raw_page_status not in {
                "SUCCEEDED",
                "PARTIAL_SUCCESS",
            }:
                raise ValueError("Textract pagination returned a non-final JobStatus.")

            self._enforce_page_limit(response)

            responses.append(response)

            next_token = self._next_token(response)

        combined = self._combine_success_pages(tuple(responses))

        result = self._parser.parse(
            job_id=normalized_job_id,
            response=combined,
        )

        if result.page_count > self._max_pages:
            raise TextractPageLimitExceededError(
                "Textract document page count "
                f"{result.page_count} exceeds configured limit "
                f"{self._max_pages}."
            )

        return result

    async def health(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "network_checked": False,
            "max_results": self.max_results,
            "max_pages": self._max_pages,
        }

    async def _get_result_page(
        self,
        *,
        job_id: str,
        next_token: str | None,
    ) -> Mapping[str, object]:
        kwargs: dict[str, object] = {
            "JobId": job_id,
            "MaxResults": self.max_results,
        }

        if next_token is not None:
            kwargs["NextToken"] = next_token

        raw_response = await asyncio.to_thread(
            self._client.get_document_text_detection,
            **kwargs,
        )

        response = self._require_mapping(
            raw_response,
            operation="GetDocumentTextDetection",
        )

        self._validate_response_shape(response)

        return response

    @staticmethod
    def _validate_response_shape(
        response: Mapping[str, object],
    ) -> None:
        raw_blocks = response.get("Blocks")

        if raw_blocks is not None and not isinstance(raw_blocks, list):
            raise ValueError("Textract response Blocks must be a list.")

        raw_metadata = response.get("DocumentMetadata")

        if raw_metadata is not None and not isinstance(
            raw_metadata,
            Mapping,
        ):
            raise ValueError("Textract response DocumentMetadata must be a mapping.")

    def _enforce_page_limit(
        self,
        response: Mapping[str, object],
    ) -> None:
        observed_pages = self._reported_page_count(response)

        if observed_pages > self._max_pages:
            raise TextractPageLimitExceededError(
                "Textract document page count "
                f"{observed_pages} exceeds configured limit "
                f"{self._max_pages}."
            )

    @classmethod
    def _combine_success_pages(
        cls,
        responses: tuple[
            Mapping[str, object],
            ...,
        ],
    ) -> dict[str, object]:
        blocks: list[object] = []
        page_count = 0
        partial_success = False

        for response in responses:
            raw_status = response.get("JobStatus")

            if raw_status == "PARTIAL_SUCCESS":
                partial_success = True

            raw_blocks = response.get("Blocks")

            if isinstance(raw_blocks, list):
                blocks.extend(raw_blocks)

            page_count = max(
                page_count,
                cls._reported_page_count(response),
            )

        status = "PARTIAL_SUCCESS" if partial_success else "SUCCEEDED"

        return {
            "JobStatus": status,
            "DocumentMetadata": {
                "Pages": page_count,
            },
            "Blocks": blocks,
        }

    @staticmethod
    def _reported_page_count(
        response: Mapping[str, object],
    ) -> int:
        page_count = 0

        raw_metadata = response.get("DocumentMetadata")

        if isinstance(raw_metadata, Mapping):
            raw_pages = raw_metadata.get("Pages")

            if (
                isinstance(raw_pages, int)
                and not isinstance(
                    raw_pages,
                    bool,
                )
                and raw_pages >= 0
            ):
                page_count = raw_pages

        raw_blocks = response.get("Blocks")

        if isinstance(raw_blocks, list):
            for raw_block in raw_blocks:
                if not isinstance(
                    raw_block,
                    Mapping,
                ):
                    continue

                raw_page = raw_block.get("Page")

                if (
                    isinstance(raw_page, int)
                    and not isinstance(
                        raw_page,
                        bool,
                    )
                    and raw_page > 0
                ):
                    page_count = max(
                        page_count,
                        raw_page,
                    )

        return page_count

    @staticmethod
    def _next_token(
        response: Mapping[str, object],
    ) -> str | None:
        raw_next_token = response.get("NextToken")

        if raw_next_token is None:
            return None

        if not isinstance(
            raw_next_token,
            str,
        ):
            raise ValueError("Textract response contains an invalid NextToken.")

        normalized = raw_next_token.strip()

        if not normalized:
            return None

        return normalized

    @staticmethod
    def _client_request_token(
        request: DocumentIntelligenceRequest,
    ) -> str:
        seed = (
            f"{request.case_id}:"
            f"{request.investigation_run_id}:"
            f"{request.document_id}:"
            f"{request.staged.bucket}:"
            f"{request.staged.object_key}:"
            f"{request.staged.sha256}"
        )

        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def _validate_staged_object(
        self,
        request: DocumentIntelligenceRequest,
    ) -> None:
        if request.staged.provider != "aws-s3":
            raise ValueError("Real Textract requires evidence staged by aws-s3.")

        if not request.staged.bucket.strip():
            raise ValueError("Real Textract requires a non-blank S3 bucket.")

        if self._expected_bucket is not None and request.staged.bucket != self._expected_bucket:
            raise ValueError("Real Textract requires evidence from the configured staging bucket.")

        if not request.staged.object_key.strip():
            raise ValueError("Real Textract requires a non-blank S3 object key.")

        if not request.staged.object_key.startswith(self._managed_prefix):
            raise ValueError("Real Textract requires evidence under the managed temporary prefix.")

    @staticmethod
    def _require_mapping(
        response: object,
        *,
        operation: str,
    ) -> Mapping[str, object]:
        if not isinstance(
            response,
            Mapping,
        ):
            raise ValueError(f"Textract {operation} returned an invalid response.")

        return response


def build_aws_document_intelligence_provider(
    *,
    settings: Settings,
    gateway: AWSIntelligenceGateway,
) -> DocumentIntelligenceProvider:
    if not settings.aws_textract_enabled:
        raise ValueError("AWS document intelligence requires aws_textract_enabled=true.")

    if settings.aws_client_mode == "mock":
        return MockTextractDocumentIntelligence()

    notification_role_arn = settings.aws_textract_notification_role_arn.strip()

    if not notification_role_arn:
        raise ValueError("AWS SDK Textract requires aws_textract_notification_role_arn.")

    client = cast(
        TextractClientProtocol,
        gateway.textract_client(),
    )

    return TextractDocumentIntelligence(
        client=client,
        max_pages=settings.aws_max_textract_pages,
        expected_bucket=settings.aws_textract_bucket,
        notification_topic_arn=(settings.aws_textract_completion_topic_arn),
        notification_role_arn=notification_role_arn,
    )


def parse_textract_response(
    *,
    job_id: str,
    response: Mapping[str, object],
) -> DocumentIntelligenceResult:
    parser = TextractResponseParser()

    return parser.parse(
        job_id=job_id,
        response=response,
    )
