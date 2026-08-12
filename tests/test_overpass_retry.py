"""Tests for the Overpass retry / mirror-fallback layer.

No real network access is performed anywhere in this module. A fake session
object stands in for ``requests.Session`` so that failure modes (429, 503,
timeouts, malformed JSON) can be reproduced deterministically.
"""

from __future__ import annotations

import unittest

import requests

from lms.config import Settings
from lms.errors import OverpassResponseError, OverpassUnavailableError
from lms.sources import overpass

BBOX = (40.1, 28.9, 40.3, 29.2)


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code=200, payload=None, headers=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"elements": []}
        self.headers = headers or {}
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """Replays a scripted list of responses/exceptions, recording each call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[str] = []

    def post(self, url, **kwargs):
        self.calls.append(url)
        if not self.script:
            raise AssertionError("FakeSession ran out of scripted responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_settings(**overrides) -> Settings:
    base = {
        "overpass_url": "https://primary.test/api",
        "overpass_mirrors": ("https://mirror-a.test/api", "https://mirror-b.test/api"),
        "max_retries": 3,
        "backoff_seconds": 0.0,
        "request_timeout": 30,
    }
    base.update(overrides)
    return Settings(**base)


class TestEndpointOrdering(unittest.TestCase):
    def test_primary_comes_first_and_duplicates_are_removed(self):
        settings = make_settings(
            overpass_mirrors=("https://primary.test/api", "https://mirror-a.test/api")
        )
        self.assertEqual(
            settings.endpoints,
            ("https://primary.test/api", "https://mirror-a.test/api"),
        )

    def test_all_three_endpoints_present_by_default(self):
        self.assertEqual(len(make_settings().endpoints), 3)


class TestRetryBehaviour(unittest.TestCase):
    def test_success_on_first_attempt_makes_one_call(self):
        session = FakeSession([FakeResponse(payload={"elements": []})])
        payload = overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        self.assertEqual(payload, {"elements": []})
        self.assertEqual(len(session.calls), 1)

    def test_retries_same_endpoint_after_503(self):
        session = FakeSession(
            [FakeResponse(status_code=503), FakeResponse(payload={"elements": []})]
        )
        overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        self.assertEqual(session.calls, ["https://primary.test/api"] * 2)

    def test_429_is_retried(self):
        session = FakeSession(
            [FakeResponse(status_code=429), FakeResponse(payload={"elements": []})]
        )
        overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        self.assertEqual(len(session.calls), 2)

    def test_falls_back_to_mirror_after_exhausting_primary(self):
        session = FakeSession(
            [
                FakeResponse(status_code=502),
                FakeResponse(status_code=502),
                FakeResponse(status_code=502),
                FakeResponse(payload={"elements": []}),
            ]
        )
        overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        self.assertEqual(session.calls[:3], ["https://primary.test/api"] * 3)
        self.assertEqual(session.calls[3], "https://mirror-a.test/api")

    def test_connection_errors_are_retried(self):
        session = FakeSession(
            [
                requests.ConnectionError("dns failure"),
                FakeResponse(payload={"elements": []}),
            ]
        )
        overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        self.assertEqual(len(session.calls), 2)

    def test_raises_when_every_endpoint_fails(self):
        session = FakeSession([FakeResponse(status_code=504) for _ in range(9)])
        with self.assertRaises(OverpassUnavailableError) as ctx:
            overpass.fetch_raw(
                BBOX, settings=make_settings(), session=session, sleep=lambda _: None
            )
        self.assertEqual(len(session.calls), 9)
        self.assertIn("mirror-b.test", str(ctx.exception))

    def test_malformed_json_skips_remaining_retries_for_that_endpoint(self):
        session = FakeSession(
            [FakeResponse(bad_json=True), FakeResponse(payload={"elements": []})]
        )
        overpass.fetch_raw(
            BBOX, settings=make_settings(), session=session, sleep=lambda _: None
        )
        # Second call must be the mirror, not a retry of the primary.
        self.assertEqual(session.calls[1], "https://mirror-a.test/api")


class TestBackoff(unittest.TestCase):
    def test_exponential_backoff_grows(self):
        first = overpass._retry_delay(None, 1, 2.0)
        second = overpass._retry_delay(None, 2, 2.0)
        third = overpass._retry_delay(None, 3, 2.0)
        self.assertEqual((first, second, third), (2.0, 4.0, 8.0))

    def test_retry_after_header_wins(self):
        response = FakeResponse(status_code=429, headers={"Retry-After": "12"})
        self.assertEqual(overpass._retry_delay(response, 1, 2.0), 12.0)

    def test_unparsable_retry_after_falls_back_to_backoff(self):
        response = FakeResponse(status_code=429, headers={"Retry-After": "soon"})
        self.assertEqual(overpass._retry_delay(response, 2, 3.0), 6.0)

    def test_sleep_is_called_between_attempts(self):
        delays: list[float] = []
        session = FakeSession(
            [FakeResponse(status_code=503), FakeResponse(payload={"elements": []})]
        )
        overpass.fetch_raw(
            BBOX,
            settings=make_settings(backoff_seconds=1.0),
            session=session,
            sleep=delays.append,
        )
        self.assertEqual(delays, [1.0])

    def test_no_sleep_after_final_attempt(self):
        delays: list[float] = []
        session = FakeSession([FakeResponse(status_code=503) for _ in range(9)])
        with self.assertRaises(OverpassUnavailableError):
            overpass.fetch_raw(
                BBOX,
                settings=make_settings(backoff_seconds=1.0),
                session=session,
                sleep=delays.append,
            )
        # 3 endpoints x 3 attempts = 9 calls, but only 2 sleeps per endpoint.
        self.assertEqual(len(delays), 6)


class TestPayloadValidation(unittest.TestCase):
    def test_non_dict_payload_rejected(self):
        with self.assertRaises(OverpassResponseError):
            overpass.parse_response([1, 2, 3])

    def test_missing_elements_key_rejected(self):
        with self.assertRaises(OverpassResponseError):
            overpass.parse_response({"version": 0.6})

    def test_remark_is_included_in_the_error_message(self):
        with self.assertRaises(OverpassResponseError) as ctx:
            overpass.parse_response({"remark": "runtime error: Query timed out"})
        self.assertIn("Query timed out", str(ctx.exception))

    def test_elements_must_be_a_list(self):
        with self.assertRaises(OverpassResponseError):
            overpass.parse_response({"elements": {}})

    def test_empty_elements_is_valid(self):
        self.assertEqual(overpass.parse_response({"elements": []}), [])


class TestCheckStatus(unittest.TestCase):
    def test_reports_one_row_per_endpoint(self):
        session = FakeSession([FakeResponse() for _ in range(3)])
        results = overpass.check_status(settings=make_settings(), session=session)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(ok for _, ok, _ in results))

    def test_failures_are_reported_not_raised(self):
        session = FakeSession(
            [
                requests.ConnectionError("boom"),
                FakeResponse(status_code=500),
                FakeResponse(),
            ]
        )
        results = overpass.check_status(settings=make_settings(), session=session)
        self.assertEqual([ok for _, ok, _ in results], [False, False, True])
        self.assertIn("ConnectionError", results[0][2])


if __name__ == "__main__":
    unittest.main()
