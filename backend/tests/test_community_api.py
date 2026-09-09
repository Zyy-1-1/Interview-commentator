"""交流区接口测试(发帖/评论/点赞/匿名身份,临时 SQLite,离线可跑)。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

TOKEN_A = "a" * 32
TOKEN_B = "b" * 32


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_community.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def _auth(token):
    return {"X-Community-Token": token}


def _post(
    client,
    token=TOKEN_A,
    title="刚结束腾讯backend一面",
    content="感受:八股占比高,求组互相模拟",
):
    return client.post(
        "/api/community/posts",
        headers=_auth(token),
        json={"title": title, "content": content},
    )


def test_write_without_token_rejected(client):
    r = client.post(
        "/api/community/posts", json={"title": "无令牌发帖", "content": "应该被拒绝"}
    )
    assert r.status_code == 401
    assert client.post("/api/community/posts/1/comments", json={"content": "x"}).status_code == 401
    assert client.post("/api/community/posts/1/like").status_code == 401


def test_create_list_detail(client):
    created = _post(client)
    assert created.status_code == 200, created.text
    post = created.json()
    assert post["title"] == "刚结束腾讯backend一面"
    assert post["author_name"].startswith("面评家用户_")
    assert post["comment_count"] == 0 and post["likes_count"] == 0

    listed = client.get("/api/community/posts", headers=_auth(TOKEN_A)).json()
    assert [p["id"] for p in listed] == [post["id"]]

    detail = client.get(f"/api/community/posts/{post['id']}").json()
    assert detail["content"] == post["content"]
    assert detail["comments"] == []
    assert client.get("/api/community/posts/999").status_code == 404


def test_same_token_stable_nickname(client):
    name_a = client.get("/api/community/me", headers=_auth(TOKEN_A)).json()["nickname"]
    name_a2 = client.get("/api/community/me", headers=_auth(TOKEN_A)).json()["nickname"]
    name_b = client.get("/api/community/me", headers=_auth(TOKEN_B)).json()["nickname"]
    assert name_a == name_a2  # 同一令牌昵称稳定
    assert name_a != name_b
    pid = _post(client).json()["id"]
    _post(client, token=TOKEN_B, title="字节数据分析实习值得去吗", content="求在过的朋友说说")
    comments = client.get(f"/api/community/posts/{pid}", headers=_auth(TOKEN_A)).json()["comments"]
    c = client.post(
        f"/api/community/posts/{pid}/comments",
        headers=_auth(TOKEN_B),
        json={"content": "同问,蹲一个"},
    )
    assert c.status_code == 200
    assert c.json()["author_name"] == name_b
    assert c.json()["post_id"] == pid
    # 评论出现在详情里并计入列表 comment_count
    detail = client.get(f"/api/community/posts/{pid}").json()
    assert [cm["content"] for cm in detail["comments"]] == ["同问,蹲一个"]
    listed = client.get("/api/community/posts").json()
    assert next(p for p in listed if p["id"] == pid)["comment_count"] == 1


def test_like_toggle_idempotent_per_identity(client):
    pid = _post(client).json()["id"]

    liked = client.post(f"/api/community/posts/{pid}/like", headers=_auth(TOKEN_A)).json()
    assert liked == {"liked": True, "likes_count": 1}
    # 同一令牌重复点赞 = 取消
    liked = client.post(f"/api/community/posts/{pid}/like", headers=_auth(TOKEN_A)).json()
    assert liked == {"liked": False, "likes_count": 0}
    # 两个身份各赞一次 → 2,且各自 liked_by_me 正确
    client.post(f"/api/community/posts/{pid}/like", headers=_auth(TOKEN_A))
    client.post(f"/api/community/posts/{pid}/like", headers=_auth(TOKEN_B))
    assert client.get(f"/api/community/posts/{pid}", headers=_auth(TOKEN_A)).json()["liked_by_me"] is True
    listed = client.get("/api/community/posts", headers=_auth(TOKEN_A)).json()
    p = next(x for x in listed if x["id"] == pid)
    assert p["likes_count"] == 2 and p["liked_by_me"] is True
    # 游客(无令牌)可看,liked_by_me 恒为 False
    guest = client.get("/api/community/posts").json()[0]
    assert guest["liked_by_me"] is False


def test_title_and_content_validation(client):
    r = client.post(
        "/api/community/posts",
        headers=_auth(TOKEN_A),
        json={"title": "短", "content": "标题过短"},
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/community/posts/{_post(client).json()['id']}/comments",
        headers=_auth(TOKEN_A),
        json={"content": ""},
    )
    assert r.status_code == 422
