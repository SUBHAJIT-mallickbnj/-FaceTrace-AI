import unittest

from pages.helper.utils import is_user_authenticated


class AuthAccessTests(unittest.TestCase):
    def test_allows_authenticated_session_state(self):
        self.assertTrue(is_user_authenticated({"authentication_status": True}))
        self.assertTrue(is_user_authenticated({"login_status": True}))
        self.assertTrue(is_user_authenticated({"username": "gagan"}))
        self.assertTrue(is_user_authenticated({"user": "gagan"}))

    def test_rejects_missing_auth_state(self):
        self.assertFalse(is_user_authenticated({}))
        self.assertFalse(is_user_authenticated({"authentication_status": False}))


if __name__ == "__main__":
    unittest.main()
