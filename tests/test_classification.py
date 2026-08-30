from services import classification_service as cs


def test_keyword_picks_plumbing():
    r = cs.classify("Water is leaking from the pipe under the basin in the washroom")
    assert r["category"] == "Plumbing"
    assert r["source"] == "keyword"
    assert r["ai_summary"]


def test_keyword_picks_it_network():
    r = cs.classify("The projector in the classroom won't connect over HDMI and wifi is down")
    assert r["category"] == "IT / Network"


def test_keyword_high_severity_on_danger_words():
    r = cs.classify("Exposed live wire near the door, someone could get a shock")
    assert r["category"] in ("Electric", "Power")
    assert r["severity"] == "high"


def test_no_keyword_hit_leaves_category_none_but_summarises():
    r = cs.classify("Something seems off in the general area near here today")
    assert r["category"] is None
    assert r["severity"] == "medium"
    assert r["ai_summary"]


def test_spam_flag_on_gibberish():
    r = cs.classify("asdf asdf test test 123")
    assert r["spam_flag"] is True
