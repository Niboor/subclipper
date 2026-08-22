def paginate_window(current: int, total: int, siblings: int = 2) -> list[int | None]:
    """0-indexed page numbers to display around `current`, always including the first
    and last page. `None` marks a gap between shown pages, meant to be rendered as an
    ellipsis, so large page counts don't require rendering a button per page."""
    if total <= 0:
        return []

    show = {0, total - 1, current}
    for offset in range(1, siblings + 1):
        show.add(current - offset)
        show.add(current + offset)
    ordered = sorted(p for p in show if 0 <= p < total)

    result: list[int | None] = []
    prev: int | None = None
    for p in ordered:
        if prev is not None and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result
