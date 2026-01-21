import unittest

from oraicle.adk import get_agent_engine_user_id
from oraicle.adk.user_identity import agent_engine_user_id, resolve_agent_engine_user_id


class DummyRequest:
    def __init__(self, headers):
        self.headers = headers


class TestUserIdentity(unittest.TestCase):
    def test_explicit_user_wins(self):
        resolved = agent_engine_user_id(
            explicit_user="Zack Mariano", default="anon"
        )
        self.assertEqual(resolved.user_id, "Zack Mariano")
        self.assertEqual(resolved.source, "explicit_user")


    def test_header_google_authenticated_user_email_is_used(self):
        req = DummyRequest(
            headers={
                "X-Goog-Authenticated-User-Email": "accounts.google.com:john.doe@corp.com"
            }
        )
        resolved = agent_engine_user_id(request=req, default="anon")
        self.assertEqual(resolved.user_id, "john.doe@corp.com")
        self.assertEqual(resolved.source, "header:x-goog-authenticated-user-email")


    def test_authorization_bearer_jwt_is_used_when_no_header_match(self):
        # JWT (alg=none) payload: {"name":"Jane Doe","email":"jane@corp.com"}
        token = "eyJhbGciOiJub25lIn0.eyJuYW1lIjoiSmFuZSBEb2UiLCJlbWFpbCI6ImphbmVAY29ycC5jb20ifQ."
        req = DummyRequest(headers={"Authorization": f"Bearer {token}"})
        resolved = agent_engine_user_id(request=req, default="anon")
        self.assertEqual(resolved.user_id, "Jane Doe")
        self.assertEqual(resolved.source, "jwt:authorization:name")


    def test_default_is_used_when_nothing_found(self):
        resolved = agent_engine_user_id(headers={}, default="anon")
        self.assertEqual(resolved.user_id, "anon")
        self.assertEqual(resolved.source, "default")

    def test_backward_compatible_alias(self):
        resolved = resolve_agent_engine_user_id(explicit_user="Someone", default="anon")
        self.assertEqual(resolved.user_id, "Someone")
        self.assertEqual(resolved.source, "explicit_user")

    def test_get_agent_engine_user_id_returns_str(self):
        user_id = get_agent_engine_user_id(explicit_user="Someone", default="anon")
        self.assertEqual(user_id, "Someone")


if __name__ == "__main__":
    unittest.main()


