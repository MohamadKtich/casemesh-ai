import json

import pytest

from casemesh.core.config import Settings
from casemesh.integrations.aws.textract_notifications import (
    TextractCompletionMessageParser,
    build_textract_completion_message_parser,
)
from casemesh.intelligence.async_processing import (
    AsyncQueueMessage,
)

TOPIC_ARN = "arn:aws:sns:eu-west-1:123456789012:casemesh-textract"

BUCKET = "synthetic-textract-bucket"

OBJECT_KEY = "casemesh-temp/case/run/document/hash"


def _payload(
    *,
    status: str = "SUCCEEDED",
    api: str = "StartDocumentTextDetection",
    bucket: str = BUCKET,
    object_key: str = OBJECT_KEY,
    timestamp: object = 1_725_000_000_000,
    job_tag: object = "document-text",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "JobId": "textract-job-1",
        "Status": status,
        "API": api,
        "Timestamp": timestamp,
        "DocumentLocation": {
            "S3ObjectName": object_key,
            "S3Bucket": bucket,
        },
    }

    if job_tag is not None:
        payload["JobTag"] = job_tag

    return payload


def _sns_body(
    *,
    payload: dict[str, object] | None = None,
    topic_arn: str = TOPIC_ARN,
    message_type: str = "Notification",
    sns_message_id: str = "sns-message-1",
) -> str:
    return json.dumps(
        {
            "Type": message_type,
            "MessageId": sns_message_id,
            "TopicArn": topic_arn,
            "Message": json.dumps(payload or _payload()),
        }
    )


def _message(
    body: str,
    *,
    message_id: str = "sqs-message-1",
    receipt_handle: str = "receipt-1",
    receive_count: int = 1,
) -> AsyncQueueMessage:
    return AsyncQueueMessage(
        message_id=message_id,
        receipt_handle=receipt_handle,
        body=body,
        receive_count=receive_count,
    )


def _parser(
    *,
    allow_raw_delivery: bool = False,
) -> TextractCompletionMessageParser:
    return TextractCompletionMessageParser(
        expected_topic_arn=TOPIC_ARN,
        expected_bucket=BUCKET,
        allow_raw_delivery=allow_raw_delivery,
    )


def test_parses_wrapped_sns_success_notification() -> None:
    event = _parser().parse(_message(_sns_body()))

    assert event.provider == "aws-textract"
    assert event.job_id == "textract-job-1"
    assert event.status == "succeeded"
    assert event.raw_status == "SUCCEEDED"
    assert event.api == "StartDocumentTextDetection"
    assert event.job_tag == "document-text"
    assert event.timestamp_ms == 1_725_000_000_000
    assert event.s3_bucket == BUCKET
    assert event.s3_object_name == OBJECT_KEY
    assert event.delivery_mode == "sns"
    assert event.topic_arn == TOPIC_ARN
    assert event.sns_message_id == "sns-message-1"
    assert event.idempotency_key == "aws-textract:textract-job-1"


@pytest.mark.parametrize(
    ("raw_status", "normalized"),
    [
        (
            "FAILED",
            "failed",
        ),
        (
            "ERROR",
            "failed",
        ),
    ],
)
def test_failure_statuses_are_normalized(
    raw_status: str,
    normalized: str,
) -> None:
    event = _parser().parse(_message(_sns_body(payload=_payload(status=raw_status))))

    assert event.status == normalized
    assert event.raw_status == raw_status


@pytest.mark.parametrize(
    "status",
    [
        "IN_PROGRESS",
        "PARTIAL_SUCCESS",
        "UNKNOWN",
        "",
    ],
)
def test_rejects_unsupported_completion_status(
    status: str,
) -> None:
    parser = _parser()

    with pytest.raises(
        ValueError,
        match="Status",
    ):
        parser.parse(_message(_sns_body(payload=_payload(status=status))))


def test_rejects_wrong_sns_topic() -> None:
    with pytest.raises(
        ValueError,
        match="unexpected SNS topic",
    ):
        _parser().parse(
            _message(_sns_body(topic_arn=("arn:aws:sns:eu-west-1:123456789012:other-topic")))
        )


@pytest.mark.parametrize(
    "message_type",
    [
        "SubscriptionConfirmation",
        "UnsubscribeConfirmation",
    ],
)
def test_rejects_non_notification_sns_envelope(
    message_type: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Type must be Notification",
    ):
        _parser().parse(_message(_sns_body(message_type=message_type)))


def test_rejects_invalid_outer_json() -> None:
    with pytest.raises(
        ValueError,
        match="valid JSON",
    ):
        _parser().parse(_message("{invalid-json"))


def test_rejects_invalid_inner_sns_json() -> None:
    body = json.dumps(
        {
            "Type": "Notification",
            "MessageId": "sns-message-1",
            "TopicArn": TOPIC_ARN,
            "Message": "{invalid-json",
        }
    )

    with pytest.raises(
        ValueError,
        match="valid JSON",
    ):
        _parser().parse(_message(body))


def test_rejects_wrong_textract_api() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported Textract completion API",
    ):
        _parser().parse(_message(_sns_body(payload=_payload(api="StartDocumentAnalysis"))))


def test_rejects_foreign_bucket() -> None:
    with pytest.raises(
        ValueError,
        match="unexpected S3 bucket",
    ):
        _parser().parse(_message(_sns_body(payload=_payload(bucket="foreign-bucket"))))


def test_rejects_object_outside_managed_prefix() -> None:
    with pytest.raises(
        ValueError,
        match="managed temporary prefix",
    ):
        _parser().parse(
            _message(_sns_body(payload=_payload(object_key=("unmanaged/document.pdf"))))
        )


def test_raw_delivery_is_rejected_by_default() -> None:
    body = json.dumps(_payload())

    with pytest.raises(
        ValueError,
        match="Raw Textract SNS delivery is disabled",
    ):
        _parser().parse(_message(body))


def test_raw_delivery_can_be_explicitly_enabled() -> None:
    event = _parser(allow_raw_delivery=True).parse(_message(json.dumps(_payload())))

    assert event.delivery_mode == "raw"
    assert event.topic_arn is None
    assert event.sns_message_id is None
    assert event.status == "succeeded"


def test_idempotency_key_survives_sqs_redelivery() -> None:
    body = _sns_body()

    first = _parser().parse(
        _message(
            body,
            message_id="sqs-delivery-1",
            receipt_handle="receipt-1",
            receive_count=1,
        )
    )

    second = _parser().parse(
        _message(
            body,
            message_id="sqs-delivery-2",
            receipt_handle="receipt-2",
            receive_count=2,
        )
    )

    assert first.idempotency_key == second.idempotency_key == "aws-textract:textract-job-1"


@pytest.mark.parametrize(
    "timestamp",
    [
        0,
        -1,
        True,
        "1725000000000",
        1.5,
    ],
)
def test_rejects_invalid_timestamp(
    timestamp: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="Timestamp",
    ):
        _parser().parse(_message(_sns_body(payload=_payload(timestamp=timestamp))))


def test_job_tag_is_optional() -> None:
    event = _parser().parse(_message(_sns_body(payload=_payload(job_tag=None))))

    assert event.job_tag is None


@pytest.mark.parametrize(
    "job_tag",
    [
        "",
        " ",
        123,
        {},
    ],
)
def test_rejects_invalid_job_tag(
    job_tag: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="JobTag",
    ):
        _parser().parse(_message(_sns_body(payload=_payload(job_tag=job_tag))))


@pytest.mark.parametrize(
    "location",
    [
        None,
        "invalid",
        [],
    ],
)
def test_rejects_invalid_document_location(
    location: object,
) -> None:
    payload = _payload()
    payload["DocumentLocation"] = location

    with pytest.raises(
        ValueError,
        match="DocumentLocation",
    ):
        _parser().parse(_message(_sns_body(payload=payload)))


def test_builder_uses_settings_and_disables_raw_delivery() -> None:
    settings = Settings(
        _env_file=None,
        aws_intelligence_enabled=True,
        aws_client_mode="mock",
        aws_async_processing_enabled=True,
        aws_textract_enabled=True,
        aws_textract_bucket=BUCKET,
        aws_textract_completion_topic_arn=TOPIC_ARN,
        aws_textract_queue_url="synthetic-queue",
    )

    parser = build_textract_completion_message_parser(settings=settings)

    event = parser.parse(_message(_sns_body()))

    assert event.status == "succeeded"

    with pytest.raises(
        ValueError,
        match="Raw Textract SNS delivery is disabled",
    ):
        parser.parse(_message(json.dumps(_payload())))


def test_constructor_rejects_unsafe_managed_prefix() -> None:
    with pytest.raises(
        ValueError,
        match="managed_prefix",
    ):
        TextractCompletionMessageParser(
            expected_topic_arn=TOPIC_ARN,
            expected_bucket=BUCKET,
            managed_prefix="../unsafe/",
        )
