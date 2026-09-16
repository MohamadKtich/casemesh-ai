import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from casemesh.core.config import Settings
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)

TextractCompletionStatus = Literal[
    "succeeded",
    "failed",
]

TextractRawCompletionStatus = Literal[
    "SUCCEEDED",
    "FAILED",
    "ERROR",
]

TextractDeliveryMode = Literal[
    "sns",
    "raw",
]


@dataclass(frozen=True, slots=True)
class TextractCompletionEvent:
    """Normalized completion notification for a Textract text-detection job."""

    provider: str
    job_id: str
    status: TextractCompletionStatus
    raw_status: TextractRawCompletionStatus
    api: str
    job_tag: str | None
    timestamp_ms: int
    s3_bucket: str
    s3_object_name: str
    delivery_mode: TextractDeliveryMode
    topic_arn: str | None = None
    sns_message_id: str | None = None

    @property
    def idempotency_key(self) -> str:
        """Stable key across SQS/SNS redelivery of the same Textract job."""

        return f"{self.provider}:{self.job_id}"


class TextractCompletionMessageParser:
    """Parse and validate Textract completion notifications delivered via SQS."""

    provider_name = "aws-textract"
    supported_api = "StartDocumentTextDetection"

    def __init__(
        self,
        *,
        expected_topic_arn: str,
        expected_bucket: str,
        managed_prefix: str = "casemesh-temp/",
        allow_raw_delivery: bool = False,
    ) -> None:
        normalized_topic_arn = expected_topic_arn.strip()

        if not normalized_topic_arn:
            raise ValueError("Textract completion expected_topic_arn must not be blank.")

        normalized_bucket = expected_bucket.strip()

        if not normalized_bucket:
            raise ValueError("Textract completion expected_bucket must not be blank.")

        normalized_prefix = managed_prefix.strip()

        if not normalized_prefix:
            raise ValueError("Textract completion managed_prefix must not be blank.")

        if not normalized_prefix.endswith("/"):
            raise ValueError("Textract completion managed_prefix must end with '/'.")

        prefix_body = normalized_prefix[:-1]

        if not prefix_body or any(part in {"", ".", ".."} for part in prefix_body.split("/")):
            raise ValueError("Textract completion managed_prefix contains an unsafe segment.")

        self._expected_topic_arn = normalized_topic_arn
        self._expected_bucket = normalized_bucket
        self._managed_prefix = normalized_prefix
        self._allow_raw_delivery = allow_raw_delivery

    def parse(
        self,
        message: AsyncQueueMessage,
    ) -> TextractCompletionEvent:
        """Parse one SQS body without acknowledging the queue message."""

        outer = self._parse_json_object(
            message.body,
            label="SQS message body",
        )

        if "Type" in outer or "Message" in outer or "TopicArn" in outer:
            return self._parse_sns_envelope(outer)

        if not self._allow_raw_delivery:
            raise ValueError("Raw Textract SNS delivery is disabled.")

        return self._parse_payload(
            outer,
            delivery_mode="raw",
            topic_arn=None,
            sns_message_id=None,
        )

    def _parse_sns_envelope(
        self,
        envelope: Mapping[str, object],
    ) -> TextractCompletionEvent:
        message_type = self._required_string(
            envelope,
            "Type",
            label="SNS envelope",
        )

        if message_type != "Notification":
            raise ValueError("SNS envelope Type must be Notification.")

        topic_arn = self._required_string(
            envelope,
            "TopicArn",
            label="SNS envelope",
        )

        if topic_arn != self._expected_topic_arn:
            raise ValueError("Textract completion notification came from an unexpected SNS topic.")

        sns_message_id = self._required_string(
            envelope,
            "MessageId",
            label="SNS envelope",
        )

        raw_message = self._required_string(
            envelope,
            "Message",
            label="SNS envelope",
            preserve_whitespace=True,
        )

        payload = self._parse_json_object(
            raw_message,
            label="SNS Message",
        )

        return self._parse_payload(
            payload,
            delivery_mode="sns",
            topic_arn=topic_arn,
            sns_message_id=sns_message_id,
        )

    def _parse_payload(
        self,
        payload: Mapping[str, object],
        *,
        delivery_mode: TextractDeliveryMode,
        topic_arn: str | None,
        sns_message_id: str | None,
    ) -> TextractCompletionEvent:
        job_id = self._required_string(
            payload,
            "JobId",
            label="Textract completion payload",
        )

        raw_status_value = self._required_string(
            payload,
            "Status",
            label="Textract completion payload",
        )

        raw_status, status = self._normalize_status(raw_status_value)

        api = self._required_string(
            payload,
            "API",
            label="Textract completion payload",
        )

        if api != self.supported_api:
            raise ValueError(f"Unsupported Textract completion API: {api}")

        job_tag = self._optional_string(
            payload,
            "JobTag",
        )

        timestamp_ms = self._timestamp_ms(payload)

        raw_location = payload.get("DocumentLocation")

        if not isinstance(
            raw_location,
            Mapping,
        ):
            raise ValueError("Textract completion DocumentLocation must be a mapping.")

        s3_bucket = self._required_string(
            raw_location,
            "S3Bucket",
            label="Textract DocumentLocation",
        )

        s3_object_name = self._required_string(
            raw_location,
            "S3ObjectName",
            label="Textract DocumentLocation",
        )

        if s3_bucket != self._expected_bucket:
            raise ValueError("Textract completion references an unexpected S3 bucket.")

        if not s3_object_name.startswith(self._managed_prefix):
            raise ValueError(
                "Textract completion references an object outside the managed temporary prefix."
            )

        return TextractCompletionEvent(
            provider=self.provider_name,
            job_id=job_id,
            status=status,
            raw_status=raw_status,
            api=api,
            job_tag=job_tag,
            timestamp_ms=timestamp_ms,
            s3_bucket=s3_bucket,
            s3_object_name=s3_object_name,
            delivery_mode=delivery_mode,
            topic_arn=topic_arn,
            sns_message_id=sns_message_id,
        )

    @staticmethod
    def _normalize_status(
        raw_status: str,
    ) -> tuple[
        TextractRawCompletionStatus,
        TextractCompletionStatus,
    ]:
        if raw_status == "SUCCEEDED":
            return (
                "SUCCEEDED",
                "succeeded",
            )

        if raw_status == "FAILED":
            return (
                "FAILED",
                "failed",
            )

        if raw_status == "ERROR":
            return (
                "ERROR",
                "failed",
            )

        raise ValueError(f"Unsupported Textract completion Status: {raw_status}")

    @staticmethod
    def _timestamp_ms(
        payload: Mapping[str, object],
    ) -> int:
        raw_timestamp = payload.get("Timestamp")

        if isinstance(
            raw_timestamp,
            bool,
        ) or not isinstance(
            raw_timestamp,
            (int, float),
        ):
            raise ValueError("Textract completion Timestamp must be a positive integer.")

        numeric_timestamp = float(raw_timestamp)

        if numeric_timestamp <= 0 or not numeric_timestamp.is_integer():
            raise ValueError("Textract completion Timestamp must be a positive integer.")

        return int(numeric_timestamp)

    @staticmethod
    def _optional_string(
        payload: Mapping[str, object],
        field_name: str,
    ) -> str | None:
        raw_value = payload.get(field_name)

        if raw_value is None:
            return None

        if not isinstance(
            raw_value,
            str,
        ):
            raise ValueError(f"Textract completion {field_name} must be a string when present.")

        normalized = raw_value.strip()

        if not normalized:
            raise ValueError(f"Textract completion {field_name} must not be blank when present.")

        return normalized

    @staticmethod
    def _required_string(
        mapping: Mapping[str, object],
        field_name: str,
        *,
        label: str,
        preserve_whitespace: bool = False,
    ) -> str:
        raw_value = mapping.get(field_name)

        if not isinstance(
            raw_value,
            str,
        ):
            raise ValueError(f"{label} {field_name} must be a string.")

        if not raw_value.strip():
            raise ValueError(f"{label} {field_name} must not be blank.")

        if preserve_whitespace:
            return raw_value

        return raw_value.strip()

    @staticmethod
    def _parse_json_object(
        text: str,
        *,
        label: str,
    ) -> Mapping[str, object]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} must contain valid JSON.") from exc

        if not isinstance(
            parsed,
            Mapping,
        ):
            raise ValueError(f"{label} must contain a JSON object.")

        return parsed


def build_textract_completion_message_parser(
    *,
    settings: Settings,
) -> TextractCompletionMessageParser:
    """Build the completion parser from CaseMesh AWS settings."""

    if not settings.aws_textract_enabled:
        raise ValueError("Textract completion parser requires aws_textract_enabled=true.")

    if not settings.aws_async_processing_enabled:
        raise ValueError("Textract completion parser requires aws_async_processing_enabled=true.")

    return TextractCompletionMessageParser(
        expected_topic_arn=(settings.aws_textract_completion_topic_arn),
        expected_bucket=settings.aws_textract_bucket,
        allow_raw_delivery=False,
    )
