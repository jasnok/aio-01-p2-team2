from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.mock_api import actor
from backend.app.services.actor_identity import actor_key
from backend.app.services.mock_store import store


@pytest.mark.parametrize("owner_role, other_role", [("USER", "GUEST"), ("GUEST", "USER")])
def test_same_id_cannot_read_modify_or_delete_other_principal_community_data(owner_role, other_role):
    identity = uuid4().hex
    owner = {"id": identity, "role": owner_role, "display_name": "synthetic owner"}
    other = dict(owner, role=other_role)
    current = [owner]
    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[actor] = lambda: current[0]
    client = TestClient(app)
    posts = []
    body = {"category": "housing", "title": "synthetic title", "content": "synthetic-private-marker",
            "post_password": "1234", "privacy_confirmed": True}
    try:
        for visibility in ("PRIVATE", "PUBLIC"):
            response = client.post("/api/questions", json=dict(body, visibility=visibility))
            assert response.status_code == 201
            posts.append(response.json()["id"])
        private, public = posts
        comment = client.post(f"/api/questions/{public}/comments", json={"content": "synthetic comment", "comment_password": "1234"})
        assert comment.status_code == 201
        assert "owner_id" not in comment.json()
        assert "owner_role" not in comment.json()
        comment_id = comment.json()["id"]
        own_comment = client.get(f"/api/questions/{public}/comments").json()["items"][0]
        assert own_comment["is_owner"] is True
        assert "owner_id" not in own_comment
        assert "owner_role" not in own_comment
        history_id = client.get("/api/history").json()["items"][0]["id"]
        notification_id = client.get("/api/notifications").json()["items"][0]["id"]
        current[0] = other
        for suffix in ("", "/comments"):
            denied = client.get(f"/api/questions/{private}{suffix}")
            assert denied.status_code == 403
            assert "synthetic-private-marker" not in denied.text
        assert client.get(f"/api/questions/{public}").status_code == 200
        public_comment = client.get(f"/api/questions/{public}/comments").json()["items"][0]
        assert public_comment["is_owner"] is False
        assert "owner_id" not in public_comment
        assert "owner_role" not in public_comment
        assert client.post(f"/api/questions/{private}/comments", json={"content": "synthetic", "comment_password": "1234"}).status_code == 403
        assert client.post(f"/api/questions/{private}/unlock", json={"post_password": "1234"}).status_code == 403
        assert client.patch(f"/api/questions/{private}", json={"title": "changed title", "content": "changed synthetic content", "post_password": "1234"}).status_code == 403
        assert client.request("DELETE", f"/api/questions/{private}", json={"post_password": "1234"}).status_code == 403
        assert client.post(f"/api/questions/{private}/resubmit", json=body).status_code == 403
        assert client.patch(f"/api/questions/{public}/comments/{comment_id}", json={"content": "changed comment", "comment_password": "1234"}).status_code == 403
        assert client.request("DELETE", f"/api/questions/{public}/comments/{comment_id}", json={"comment_password": "1234"}).status_code == 403
        assert client.get("/api/history").json()["items"] == []
        assert client.get(f"/api/history/{history_id}").status_code == 404
        assert client.delete(f"/api/history/{history_id}").status_code == 404
        assert client.get("/api/notifications").json()["items"] == []
        assert client.get("/api/notifications/unread-count").json()["count"] == 0
        assert client.patch(f"/api/notifications/{notification_id}/read").status_code == 404
        assert client.delete(f"/api/notifications/{notification_id}").status_code == 404
        assert client.patch("/api/notifications/read-all").status_code == 200
        assert client.delete("/api/notifications/read-items").status_code == 204
        current[0] = owner
        assert client.get(f"/api/questions/{private}").status_code == 200
        assert client.get(f"/api/history/{history_id}").status_code == 200
        assert client.get("/api/notifications/unread-count").json()["count"] > 0
        assert client.patch(f"/api/questions/{public}/comments/{comment_id}", json={"content": "valid owner edit", "comment_password": "1234"}).status_code == 200
        current[0] = {"id": "synthetic-admin", "role": "ADMIN", "display_name": "admin"}
        assert client.get(f"/api/questions/{private}").status_code == 200
        assert any(row["action"] == "PRIVATE_QUESTION_VIEWED" and row["target_id"] == private for row in store.audit_logs)
        assert client.patch(f"/api/questions/{public}/comments/{comment_id}", json={"content": "admin edit"}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        for post in posts:
            store.questions.pop(post, None)
        for key, row in list(store.comments.items()):
            if row["question_id"] in posts:
                store.comments.pop(key)
        for principal in (owner, other):
            store.history.pop(actor_key(principal), None)
            store.notifications.pop(actor_key(principal), None)
        store.audit_logs[:] = [row for row in store.audit_logs if row["target_id"] not in posts]
