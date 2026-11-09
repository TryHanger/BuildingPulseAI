def test_quality_and_rules(client):
    scenarios_resp = client.get("/api/scenarios")
    assert scenarios_resp.status_code == 200
    items = scenarios_resp.json()["items"]
    assert len(items) > 0

    scenario_id = items[0]["id"]

    # 1. Test data quality report
    q_resp = client.get(f"/api/data-quality?scenario_id={scenario_id}")
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert "time_monotonic" in q_data
    assert "metrics" in q_data
    assert len(q_data["metrics"]) > 0

    # 2. Test diagnostic rule execution
    rules_resp = client.post(
        "/api/diagnostics/run-rules",
        json={"scenario_id": scenario_id}
    )
    assert rules_resp.status_code == 200
    rules_data = rules_resp.json()
    assert rules_data["algorithm_type"] == "RULE_BASELINE"
    assert "events" in rules_data

    # 3. Test retrieving events
    ev_resp = client.get(f"/api/diagnostics/events?scenario_id={scenario_id}")
    assert ev_resp.status_code == 200
    events = ev_resp.json()
    assert isinstance(events, list)
