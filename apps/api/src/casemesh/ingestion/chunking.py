def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines)
    while "\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n", "\n\n")
    return normalized.strip()


def chunk_text(
    text: str,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 200,
) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and < max_chars")

    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        hard_end = min(start + max_chars, text_length)
        end = hard_end

        if hard_end < text_length:
            candidates = [
                normalized.rfind("\n\n", start, hard_end),
                normalized.rfind("\n", start, hard_end),
                normalized.rfind(". ", start, hard_end),
                normalized.rfind(" ", start, hard_end),
            ]
            split_at = max(candidates)
            if split_at > start + (max_chars // 2):
                end = split_at + (2 if normalized[split_at : split_at + 2] == ". " else 1)

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = max(0, end - overlap_chars)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks
