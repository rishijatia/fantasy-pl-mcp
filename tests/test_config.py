"""Tests for environment-driven configuration values."""

import importlib

import fpl_mcp.config as config


def _reload_with_env(monkeypatch, value):
    monkeypatch.setenv("LEAGUE_RESULTS_LIMIT", value)
    importlib.reload(config)
    return config.LEAGUE_RESULTS_LIMIT


def test_league_results_limit_default(monkeypatch):
    monkeypatch.delenv("LEAGUE_RESULTS_LIMIT", raising=False)
    importlib.reload(config)
    assert config.LEAGUE_RESULTS_LIMIT == 50


def test_league_results_limit_env_override(monkeypatch):
    assert _reload_with_env(monkeypatch, "30") == 30


def test_league_results_limit_clamped_to_hard_cap(monkeypatch):
    assert _reload_with_env(monkeypatch, "5000") == config.LEAGUE_RESULTS_HARD_CAP


def teardown_module():
    # Leave the module in its default state for other tests
    importlib.reload(config)
