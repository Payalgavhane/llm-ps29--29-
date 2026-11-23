"""Offline tests (no API key needed): python test_grammar_tutor.py"""
from grammar_tutor import (GrammarTutorError, build_user_prompt, correct_paragraph,
                           highlight, parse_response, tally_categories)

GOOD = '{"corrected_text":"I went home.","errors":[{"error":"go","correction":"went","rule":"Use past tense for finished actions.","category":"Tense"}],"tip":"Watch tenses."}'

def test_parse_plain():
    r = parse_response(GOOD)
    assert r["corrected_text"] == "I went home." and r["errors"][0]["category"] == "Tense"

def test_parse_fenced():
    assert parse_response("```json\n" + GOOD + "\n```")["errors"][0]["error"] == "go"

def test_parse_with_chatter():
    assert len(parse_response("Sure! " + GOOD + " Hope it helps")["errors"]) == 1

def test_parse_bad():
    try:
        parse_response("not json at all")
        assert False
    except GrammarTutorError:
        pass

def test_highlight_and_escape():
    out = highlight("I go <b> home. I go.", ["go", "go"], "#fff", "#000")
    assert out.count("<mark") == 2 and "&lt;b&gt;" in out

def test_empty_input():
    try:
        correct_paragraph("   ", "Gemini", "key")
        assert False
    except GrammarTutorError:
        pass

def test_missing_key():
    try:
        correct_paragraph("I go home", "Gemini", "")
        assert False
    except GrammarTutorError:
        pass

def test_prompt_and_tally():
    assert "Beginner" in build_user_prompt("hi", "Beginner", "Marathi") and "Marathi" in build_user_prompt("hi", "Beginner", "Marathi")
    assert tally_categories(parse_response(GOOD)["errors"])["Tense"] == 1

def test_fallback_and_retry():
    import grammar_tutor as g
    calls = []
    def fake(system, user, provider, key, model=None, timeout=60):
        calls.append(model)
        if model == "bad-model":
            raise g.GrammarTutorError("API error 404.", status=404)
        if len(calls) == 2:
            raise g.GrammarTutorError("API error 503.", status=503)
        return GOOD
    orig, orig_sleep = g.call_llm, g.time.sleep
    g.call_llm, g.time.sleep = fake, lambda s: None
    try:
        r = g.correct_paragraph("I go home", "Gemini", "key", model="bad-model")
    finally:
        g.call_llm, g.time.sleep = orig, orig_sleep
    assert r["corrected_text"] == "I went home." and calls[0] == "bad-model" and len(calls) >= 3

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
