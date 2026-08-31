from sqlalchemy import DateTime

from casemesh.db.models import CaseDocument, InvestigationRun, Policy


def assert_timezone_aware(column_type: object) -> None:
    assert isinstance(column_type, DateTime)
    assert column_type.timezone is True


def test_ingestion_datetime_column_is_timezone_aware() -> None:
    assert_timezone_aware(CaseDocument.__table__.c.ingested_at.type)


def test_policy_datetime_columns_are_timezone_aware() -> None:
    assert_timezone_aware(Policy.__table__.c.effective_from.type)
    assert_timezone_aware(Policy.__table__.c.effective_to.type)


def test_investigation_datetime_columns_are_timezone_aware() -> None:
    assert_timezone_aware(InvestigationRun.__table__.c.started_at.type)
    assert_timezone_aware(InvestigationRun.__table__.c.completed_at.type)
