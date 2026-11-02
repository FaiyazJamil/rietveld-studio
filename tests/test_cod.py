from __future__ import annotations

import json

import pytest

from rietveld_studio.cod import CODClient


def test_cod_uses_required_elements_and_element_count_not_nel(tmp_path, monkeypatch):
    client = CODClient(tmp_path)
    requests = []
    def get(endpoint, params=None):
        requests.append(params)
        return json.dumps([
            {"file": "1000001", "formula": "Fe Li O4 P", "sg": "P n m a"},
            {"file": "1000002", "formula": "Fe2 Li3 O12 P3", "sg": "R -3"},
        ]).encode()
    monkeypatch.setattr(client, "_get", get)
    candidates = client.search("LiFePO4")
    assert requests[0]["strictmin"] == requests[0]["strictmax"] == "4"
    assert {requests[0][f"el{i}"] for i in range(1, 5)} == {"Fe", "Li", "O", "P"}
    assert not any(key.startswith("nel") for key in requests[0])
    assert candidates[0].cod_id == "1000001"
    assert candidates[0].distance == 0
    assert candidates[1].distance > 0


def test_cod_cache_fallback_is_disclosed(tmp_path, monkeypatch):
    client = CODClient(tmp_path)
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: b'[{"file":"1000001","formula":"Si"}]')
    first = client.search("Si")
    def offline(*args, **kwargs):
        raise ConnectionError("offline")
    monkeypatch.setattr(client, "_get", offline)
    second = client.search("Si")
    assert first == second
    assert "cached" in client.last_notice
    with pytest.raises(ConnectionError):
        client.search("LiFePO4")


def test_cod_html_is_not_accepted_as_json(tmp_path, monkeypatch):
    client = CODClient(tmp_path)
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: b"<html>temporary error</html>")
    with pytest.raises(json.JSONDecodeError):
        client.search("Si", use_cache=False)

