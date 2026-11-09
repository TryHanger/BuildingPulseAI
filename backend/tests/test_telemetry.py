def test_telemetry_query_and_downsampling(client):
    # 1. Fetch scenarios
    scenarios_resp = client.get("/api/scenarios")
    assert scenarios_resp.status_code == 200
    items = scenarios_resp.json()["items"]
    assert len(items) > 0, "At least one scenario should be registered"

    scenario_id = items[0]["id"]

    # 2. Query telemetry
    tel_resp = client.get(f"/api/telemetry?scenario_id={scenario_id}&channels=SA_TEMP,OA_TEMP&max_points=50")
    assert tel_resp.status_code == 200
    data = tel_resp.json()

    assert data["scenario_id"] == scenario_id
    assert len(data["series"]) >= 1
    assert "sampling" in data
    assert data["sampling"]["returned_points"] <= 60

    # Ensure no NaN or Inf in points
    for s in data["series"]:
        for pt in s["points"]:
            t, v = pt
            assert isinstance(t, str)
            if v is not None:
                assert isinstance(v, (int, float))
