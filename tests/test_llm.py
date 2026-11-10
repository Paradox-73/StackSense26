"""The LLM client: configuration, model fallback, JSON extraction and the disk cache. No network."""
import json

import pytest

from engine import llm

MSG = [{"role": "user", "content": "hello"}]


def test_no_key_means_disabled_and_chat_raises():
    assert llm.available() is False
    with pytest.raises(llm.LLMError, match="no API key"):
        llm.chat(MSG)


def test_key_from_environment_and_from_dotenv_file(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "abc")
    assert llm.available()
    monkeypatch.delenv("OPENROUTER_API_KEY")
    env = tmp_path / ".env"
    env.write_text('# comment\nSTACKSENSE_LLM_API_KEY="from-file"\nSTACKSENSE_LLM_MODELS=x/y:free, z/w\n', encoding="utf-8")
    monkeypatch.setattr(llm, "DOTENV_PATH", env)
    assert llm.available()
    assert llm.models() == ["x/y:free", "z/w"]


def test_default_model_chain_and_base_url():
    assert llm.models()[0] == "gemini-3.5-flash-lite" and len(llm.models()) == 3
    assert llm.base_url() == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_falls_back_to_next_model_on_429_then_5xx_then_timeout(fake_llm, monkeypatch):
    monkeypatch.setenv("STACKSENSE_LLM_MODELS", "m/1,m/2,m/3,m/4")
    fake = fake_llm((429, {}), (503, {}), TimeoutError(), {"ok": 1})
    reply = llm.chat(MSG)
    assert json.loads(reply.text) == {"ok": 1}
    assert reply.model == "m/4" and not reply.cached
    assert [c[1]["model"] for c in fake.calls] == ["m/1", "m/2", "m/3", "m/4"]


def test_404_moves_on_and_all_models_failing_raises_without_the_key(fake_llm):
    fake_llm((404, {}), (429, {}))
    with pytest.raises(llm.LLMError) as err:
        llm.chat(MSG)
    assert "test-key-not-real" not in str(err.value)


def test_json_mode_is_dropped_for_a_model_that_rejects_it(fake_llm):
    fake = fake_llm((400, {}), {"a": 1})
    assert json.loads(llm.chat(MSG).text) == {"a": 1}
    assert "response_format" in fake.calls[0][1] and "response_format" not in fake.calls[1][1]


def test_empty_reply_counts_as_failure(fake_llm):
    fake = fake_llm((200, {"choices": [{"message": {"content": None}}]}), {"a": 1})
    assert llm.chat(MSG).model == "model/b:free" and len(fake.calls) == 2


def test_cache_hit_makes_no_request_and_is_one_file_per_entry(fake_llm):
    fake = fake_llm({"a": 1})
    first = llm.chat(MSG)
    second = llm.chat(MSG)
    assert second.cached and second.text == first.text and len(fake.calls) == 1
    files = [f for f in llm.CACHE_DIR.glob("*.json") if not f.name.startswith(".")]
    assert len(files) == 1
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["messages"] == MSG and "test-key" not in files[0].read_text(encoding="utf-8")
    llm.chat([{"role": "user", "content": "different"}])
    assert len(fake.calls) == 2 and len([f for f in llm.CACHE_DIR.glob("*.json") if not f.name.startswith(".")]) == 2


def test_cache_key_depends_on_model_chain(fake_llm, monkeypatch):
    fake = fake_llm({"a": 1})
    llm.chat(MSG)
    monkeypatch.setenv("STACKSENSE_LLM_MODELS", "other/model")
    llm.chat(MSG)
    assert len(fake.calls) == 2


@pytest.mark.parametrize("text", ['{"a": 1}', '```json\n{"a": 1}\n```', 'Sure! Here it is: {"a": 1} Hope that helps.'])
def test_extract_json_is_tolerant(text):
    assert llm.extract_json(text) == {"a": 1}


def test_chat_json_rejects_text_without_an_object(fake_llm):
    fake_llm("no json here")
    with pytest.raises(llm.LLMError, match="JSON object"):
        llm.chat_json(MSG)


def test_daily_limit_stops_real_requests_but_cached_replies_still_work(fake_llm, monkeypatch):
    monkeypatch.setenv("STACKSENSE_LLM_DAILY_LIMIT", "2")
    fake = fake_llm({"a": 1})
    assert llm.available()
    llm.chat(MSG)
    llm.chat([{"role": "user", "content": "second"}])
    assert llm.requests_today() == 2 and len(fake.calls) == 2
    assert llm.available() is False
    assert json.loads(llm.chat(MSG).text) == {"a": 1}  # served from the cache
    with pytest.raises(llm.LLMError, match="daily limit"):
        llm.chat([{"role": "user", "content": "third"}])
    assert len(fake.calls) == 2


def test_daily_counter_restarts_on_a_new_day_and_zero_means_no_limit(fake_llm, monkeypatch):
    monkeypatch.setenv("STACKSENSE_LLM_DAILY_LIMIT", "1")
    fake_llm({"a": 1})
    llm.chat(MSG)
    assert not llm.available()
    llm._usage_path().write_text(json.dumps({"date": "2001-01-01", "count": 99}), encoding="utf-8")
    assert llm.available() and llm.requests_today() == 0
    monkeypatch.setenv("STACKSENSE_LLM_DAILY_LIMIT", "0")
    llm._count_request()
    assert llm.available()


def test_default_daily_limit_and_bad_value(monkeypatch):
    assert llm.daily_limit() == 200
    monkeypatch.setenv("STACKSENSE_LLM_DAILY_LIMIT", "lots")
    assert llm.daily_limit() == 200


def test_failed_requests_are_counted_too(fake_llm):
    fake_llm((429, {}))
    with pytest.raises(llm.LLMError):
        llm.chat(MSG)
    assert llm.requests_today() == 2  # one request per model in the chain
