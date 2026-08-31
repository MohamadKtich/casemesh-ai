class DuplicateCaseNumberError(Exception):
    """Raised when a case number already exists."""

    def __init__(self, case_number: str) -> None:
        self.case_number = case_number
        super().__init__(f"Case number already exists: {case_number}")
