from casemesh.workflows.checkpoints import to_psycopg_url


def test_asyncpg_url_is_converted_for_psycopg() -> None:
    source = "postgresql+asyncpg://casemesh:secret@localhost:5432/casemesh"

    assert to_psycopg_url(source) == ("postgresql://casemesh:secret@localhost:5432/casemesh")
