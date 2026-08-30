from db import notices


def test_publish_and_list(memstore):
    n = notices.create("Water shutdown", "10am-2pm Block B", "admin")
    assert notices.list_published() == []
    notices.publish(n["id"], True)
    pub = notices.list_published()
    assert [x["title"] for x in pub] == ["Water shutdown"]


def test_expired_notice_excluded(memstore):
    n = notices.create("Old", "body", "admin", is_published=True, expires_at=50.0)
    assert notices.list_published(now=100.0) == []
    assert notices.list_published(now=10.0)[0]["id"] == n["id"]
