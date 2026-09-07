from frontend.components import integration_smoke_test


def test_team_connection_checks_cover_all_services(monkeypatch) -> None:
    monkeypatch.setattr(
        integration_smoke_test,
        "_check_http",
        lambda name, url: {"name": name, "ok": True, "message": url, "elapsed_ms": 1, "detail": {}},
    )
    monkeypatch.setattr(
        integration_smoke_test,
        "_check_tcp",
        lambda name, host, port: {"name": name, "ok": True, "message": f"{host}:{port}", "elapsed_ms": 1, "detail": None},
    )

    results = integration_smoke_test.run_team_connection_checks()

    assert [result["name"] for result in results] == ["Frontend", "Backend", "MCP", "DB"]
    assert all(result["ok"] for result in results)
    assert results[0]["message"].endswith(":8501/_stcore/health")
    assert results[1]["message"].endswith(":8000/health")
    assert results[2]["message"].endswith(":8011/health")
    assert results[3]["message"].endswith(":5434")


def test_http_check_returns_failure_without_raising(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise integration_smoke_test.httpx.ConnectError("연결 거부")

    monkeypatch.setattr(integration_smoke_test.httpx, "get", fail)
    result = integration_smoke_test._check_http("Backend", "http://example.invalid/health")

    assert not result["ok"]
    assert result["name"] == "Backend"
