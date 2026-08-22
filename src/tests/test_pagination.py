from src.utils.pagination import paginate_window


def test_empty():
    assert paginate_window(current=0, total=0) == []


def test_single_page():
    assert paginate_window(current=0, total=1) == [0]


def test_small_total_shows_everything_no_ellipsis():
    assert paginate_window(current=2, total=5) == [0, 1, 2, 3, 4]


def test_large_total_at_start_collapses_tail():
    assert paginate_window(current=0, total=171) == [0, 1, 2, None, 170]


def test_large_total_in_middle_collapses_both_sides():
    assert paginate_window(current=85, total=171) == [0, None, 83, 84, 85, 86, 87, None, 170]


def test_large_total_at_end_collapses_head():
    assert paginate_window(current=170, total=171) == [0, None, 168, 169, 170]


def test_no_duplicate_or_single_gap_page():
    # When the sibling window touches the first/last page exactly, there should be no
    # dangling ellipsis hiding just a single page.
    assert paginate_window(current=2, total=6) == [0, 1, 2, 3, 4, 5]


def test_custom_sibling_count():
    assert paginate_window(current=10, total=21, siblings=1) == [0, None, 9, 10, 11, None, 20]
