"""Tests for Settings validation and environment parsing."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

from lms.config import DEFAULT_OVERPASS_MIRRORS, Settings
from lms.errors import ConfigError

ENV_KEYS = (
    "OVERPASS_URL",
    "OVERPASS_MIRRORS",
    "REQUEST_TIMEOUT",
    "MAX_RETRIES",
    "BACKOFF_SECONDS",
    "REQUESTS_CA_BUNDLE",
    "CA_BUNDLE",
    "DB_PATH",
    "GOOGLE_PLACES_API_KEY",
    "USER_AGENT",
)


@contextmanager
def clean_env(**overrides):
    """Run a block with a predictable environment, then restore it."""
    saved = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update({k: v for k, v in overrides.items() if v is not None})
    try:
        yield
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if saved[key] is not None:
                os.environ[key] = saved[key]


class TestSettingsValidation(unittest.TestCase):
    def test_defaults_are_valid(self):
        settings = Settings()
        self.assertGreater(settings.request_timeout, 0)
        self.assertGreaterEqual(settings.max_retries, 1)

    def test_zero_timeout_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(request_timeout=0)

    def test_negative_timeout_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(request_timeout=-5)

    def test_zero_retries_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(max_retries=0)

    def test_negative_backoff_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(backoff_seconds=-1.0)

    def test_non_http_url_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(overpass_url="ftp://overpass.test/api")

    def test_mirror_with_bad_scheme_rejected(self):
        with self.assertRaises(ConfigError):
            Settings(overpass_mirrors=("not-a-url",))

    def test_http_url_accepted(self):
        Settings(overpass_url="http://localhost:12345/api/interpreter")


class TestEndpoints(unittest.TestCase):
    def test_default_mirrors_are_wired_in(self):
        self.assertEqual(len(Settings().endpoints), 1 + len(DEFAULT_OVERPASS_MIRRORS))

    def test_empty_mirrors_leaves_only_the_primary(self):
        self.assertEqual(len(Settings(overpass_mirrors=()).endpoints), 1)


class TestFromEnv(unittest.TestCase):
    def test_reads_defaults_when_env_is_empty(self):
        with clean_env():
            settings = Settings.from_env()
        self.assertEqual(settings.max_retries, 3)

    def test_parses_comma_separated_mirrors(self):
        with clean_env(OVERPASS_MIRRORS="https://a.test/api, https://b.test/api"):
            settings = Settings.from_env()
        self.assertEqual(
            settings.overpass_mirrors, ("https://a.test/api", "https://b.test/api")
        )

    def test_parses_numeric_settings(self):
        with clean_env(MAX_RETRIES="5", BACKOFF_SECONDS="0.5", REQUEST_TIMEOUT="45"):
            settings = Settings.from_env()
        self.assertEqual(settings.max_retries, 5)
        self.assertEqual(settings.backoff_seconds, 0.5)
        self.assertEqual(settings.request_timeout, 45)

    def test_invalid_integer_raises_config_error(self):
        with clean_env(MAX_RETRIES="many"):
            with self.assertRaises(ConfigError):
                Settings.from_env()

    def test_invalid_float_raises_config_error(self):
        with clean_env(BACKOFF_SECONDS="slow"):
            with self.assertRaises(ConfigError):
                Settings.from_env()

    def test_requests_ca_bundle_is_honoured(self):
        with clean_env(REQUESTS_CA_BUNDLE="/tmp/ca.pem"):
            self.assertEqual(Settings.from_env().ca_bundle, "/tmp/ca.pem")

    def test_ca_bundle_fallback_variable(self):
        with clean_env(CA_BUNDLE="/tmp/other.pem"):
            self.assertEqual(Settings.from_env().ca_bundle, "/tmp/other.pem")

    def test_api_key_is_not_logged_in_repr(self):
        with clean_env(GOOGLE_PLACES_API_KEY="super-secret-value"):
            settings = Settings.from_env()
        self.assertNotIn("super-secret-value", repr(settings))


if __name__ == "__main__":
    unittest.main()
