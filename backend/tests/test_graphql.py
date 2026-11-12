def gql(client, query: str, variables: dict | None = None) -> dict:
    response = client.post("/graphql", json={"query": query, "variables": variables or {}})
    assert response.status_code == 200
    return response.json()


def test_summary_matches_rest(client, seeded):
    rest = client.get("/v1/stats/summary", params={"window_minutes": 60}).json()
    result = gql(
        client,
        "{ summary(windowMinutes: 60) { sessions errors errorRate adFillRate "
        "avgStartupMs p95StartupMs rebufferRatio avgBitrateKbps } }",
    )
    summary = result["data"]["summary"]
    assert summary["sessions"] == rest["sessions"] == 4
    assert summary["errorRate"] == rest["error_rate"]
    assert summary["adFillRate"] == rest["ad_fill_rate"]
    assert summary["p95StartupMs"] == rest["p95_startup_ms"]
    assert summary["rebufferRatio"] == rest["rebuffer_ratio"]


def test_single_query_fetches_dashboard_data(client, seeded):
    result = gql(
        client,
        """query Dash($w: Int!) {
          summary(windowMinutes: $w) { sessions }
          timeseries(windowMinutes: $w, stepMinutes: 5) { ts sessions errors }
          breakdown(dimension: CDN, windowMinutes: $w) { key sessions }
          topErrors(windowMinutes: $w, limit: 3) { errorCode count }
        }""",
        {"w": 60},
    )
    assert "errors" not in result
    data = result["data"]
    assert data["summary"]["sessions"] == 4
    assert sum(p["sessions"] for p in data["timeseries"]) == 4
    assert {r["key"] for r in data["breakdown"]} == {"akamai", "fastly"}
    assert data["topErrors"] == [{"errorCode": "NETWORK_TIMEOUT", "count": 1}]


def test_invalid_window_is_a_graphql_error(client):
    result = gql(client, "{ summary(windowMinutes: 0) { sessions } }")
    assert result["errors"][0]["message"].startswith("window_minutes must be")


def test_invalid_enum_is_rejected(client):
    result = gql(client, "{ breakdown(dimension: PASSWORD) { key } }")
    assert "errors" in result
