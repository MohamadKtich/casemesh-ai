from casemesh.services.answers import extract_citation_labels


def test_extract_citation_labels_deduplicates_in_order() -> None:
    answer = "Claim one [E2]. Claim two [E1] [E2]."

    assert extract_citation_labels(answer) == ["E2", "E1"]


def test_extract_citation_labels_ignores_non_evidence_markers() -> None:
    answer = "Claim [X1]. Another claim [E3]."

    assert extract_citation_labels(answer) == ["E3"]
