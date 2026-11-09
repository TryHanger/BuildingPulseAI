from research.study.assignment import allocate
from research.study.score import score


def test_qa_and_review_exports_cannot_contribute_to_research_scores():
    assignments = list(allocate(20261108, 2))
    result = score(assignments, [{"collection_mode": "QA_ONLY"}, {"collection_mode": "REVIEW_ONLY"}], {})
    assert result["evaluation"] == "NOT_EXECUTED"
    assert result["excluded_qa_or_review"] == 2
    assert result["participant_contrast_c_minus_b_assigned"] == {}
    assert result["completed_time_median_ms"] == {}
    assert result["arms"] == {arm: {"assigned": 24, "no_export": 24} for arm in "ABC"}


def test_assignment_contains_six_slots_with_six_visits_each():
    allocation = list(allocate(7, 1))
    assert len(allocation) == 6
    assert all(len(person["visits"]) == 6 for person in allocation)
