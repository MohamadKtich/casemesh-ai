import pytest

from casemesh.integrations.aws.textract import (
    TextractDocumentIntelligence,
    TextractPageLimitExceededError,
    TextractPaginationLoopError,
)


class SequentialTextractClient:
    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def start_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        return {
            "JobId": "synthetic-job",
        }

    def get_document_text_detection(
        self,
        **kwargs: object,
    ) -> object:
        self.calls.append(dict(kwargs))

        if not self.responses:
            raise AssertionError("Unexpected additional Textract pagination call.")

        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_paginated_result_aggregates_lines_in_order() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [
                    {
                        "BlockType": "LINE",
                        "Page": 1,
                        "Text": "First page line",
                        "Confidence": 99.0,
                    }
                ],
                "NextToken": "page-two",
            },
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [
                    {
                        "BlockType": "LINE",
                        "Page": 2,
                        "Text": "Second page line",
                        "Confidence": 98.0,
                    }
                ],
            },
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    result = await provider.get("synthetic-job")

    assert result.status == "succeeded"
    assert result.page_count == 2
    assert result.text == ("First page line\nSecond page line")

    assert [line.page_number for line in result.lines] == [
        1,
        2,
    ]

    assert client.calls == [
        {
            "JobId": "synthetic-job",
            "MaxResults": 1000,
        },
        {
            "JobId": "synthetic-job",
            "MaxResults": 1000,
            "NextToken": "page-two",
        },
    ]


@pytest.mark.asyncio
async def test_partial_success_warning_survives_pagination() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [],
                "NextToken": "next",
            },
            {
                "JobStatus": "PARTIAL_SUCCESS",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [
                    {
                        "BlockType": "LINE",
                        "Page": 2,
                        "Text": "Partial result",
                        "Confidence": 90.0,
                    }
                ],
            },
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    result = await provider.get("synthetic-job")

    assert result.status == "succeeded"
    assert result.warnings == ("PARTIAL_SUCCESS",)
    assert result.text == "Partial result"


@pytest.mark.asyncio
async def test_metadata_page_limit_rejects_before_followup_call() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 21,
                },
                "Blocks": [],
                "NextToken": "should-not-be-used",
            }
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    with pytest.raises(
        TextractPageLimitExceededError,
        match="21 exceeds configured limit 20",
    ):
        await provider.get("synthetic-job")

    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_block_page_limit_rejects_without_metadata() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "Blocks": [
                    {
                        "BlockType": "LINE",
                        "Page": 21,
                        "Text": "Too far",
                        "Confidence": 99.0,
                    }
                ],
            }
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    with pytest.raises(
        TextractPageLimitExceededError,
        match="21 exceeds configured limit 20",
    ):
        await provider.get("synthetic-job")


@pytest.mark.asyncio
async def test_repeated_next_token_is_rejected() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [],
                "NextToken": "repeat-token",
            },
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [],
                "NextToken": "repeat-token",
            },
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    with pytest.raises(
        TextractPaginationLoopError,
        match="repeated NextToken",
    ):
        await provider.get("synthetic-job")

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_invalid_next_token_shape_is_rejected() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 1,
                },
                "Blocks": [],
                "NextToken": 123,
            }
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    with pytest.raises(
        ValueError,
        match="invalid NextToken",
    ):
        await provider.get("synthetic-job")


@pytest.mark.asyncio
async def test_paginated_non_final_status_is_rejected() -> None:
    client = SequentialTextractClient(
        [
            {
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [],
                "NextToken": "next",
            },
            {
                "JobStatus": "IN_PROGRESS",
                "DocumentMetadata": {
                    "Pages": 2,
                },
                "Blocks": [],
            },
        ]
    )

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=20,
    )

    with pytest.raises(
        ValueError,
        match="non-final JobStatus",
    ):
        await provider.get("synthetic-job")


def test_constructor_rejects_nonpositive_page_limit() -> None:
    client = SequentialTextractClient([])

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        TextractDocumentIntelligence(
            client=client,
            max_pages=0,
        )


@pytest.mark.asyncio
async def test_health_exposes_configured_page_limit() -> None:
    client = SequentialTextractClient([])

    provider = TextractDocumentIntelligence(
        client=client,
        max_pages=7,
    )

    health = await provider.health()

    assert health["max_pages"] == 7
    assert health["max_results"] == 1000
    assert health["network_checked"] is False
