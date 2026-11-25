from __future__ import annotations

import pytest

from starvellapi._http import Http, parse_session
from starvellapi._limits import RateLimiter, group_of
from starvellapi._transport import TransportError, make_proxy_url
from starvellapi.errors import (
    APIError,
    BotCheckError,
    CooldownError,
    NetworkError,
    RateLimitError,
    TwoFactorRequiredError,
    UnauthorizedError,
)

from .conftest import html_response, json_response


def make_http(transport, **kw) -> Http:
    return Http("s3cr3t", transport=transport, **kw)


def test_parse_session():
    assert parse_session("abc") == "abc"
    assert parse_session(" a=1; session=xyz; b=2 ") == "xyz"
    assert parse_session("a=1; b=2") == ""
    assert parse_session("base64value==") == "base64value=="
    with pytest.raises(TypeError):
        Http("a=1; b=2", transport=object())


def test_proxy_url():
    assert make_proxy_url(None) is None
    assert make_proxy_url("1.2.3.4:80") == "http://1.2.3.4:80"
    assert make_proxy_url("1.2.3.4:80:u:p") == "http://u:p@1.2.3.4:80"
    assert make_proxy_url("u:p@1.2.3.4:80") == "http://u:p@1.2.3.4:80"
    assert make_proxy_url("socks5://u:p@h:1") == "socks5://u:p@h:1"


def test_limit_groups():
    assert group_of("/api/messages/send") == "messages_send"
    assert group_of("/api/messages/list-v2") == "messages_list"
    assert group_of("/api/chats/list-pinned") == "chats"
    assert group_of("/api/chats/read") == "default"
    assert group_of("/api/offers/123/update") == "offers_update"
    assert group_of("/api/offers/abc/partial-update") == "offers_partial_update"
    assert group_of("/api/orders/list") == "orders_list"


async def test_limiter_waits_when_window_full(clock):
    limiter = RateLimiter({"messages_send": (2, 60)})
    for _ in range(2):
        await limiter.acquire("/api/messages/send")
    start = clock.now
    await limiter.acquire("/api/messages/send")
    assert clock.now - start == pytest.approx(60)


async def test_post_without_body_sends_empty_object(transport, clock):
    transport.add("POST", "/api/chats/list-pinned", [])
    http = make_http(transport)
    assert await http.request("POST", "/api/chats/list-pinned") == []
    call = transport.calls[0]
    assert call["json"] == {}
    assert call["headers"]["cookie"] == "session=s3cr3t"


async def test_unauthorized_on_any_request(transport, clock):
    transport.add("GET", "/api/orders/1", json_response({"success": False, "message": "Forbidden Exception", "data": {"code": "SESSION_NOT_FOUND"}}, 403))
    with pytest.raises(UnauthorizedError):
        await make_http(transport).request("GET", "/api/orders/1")


async def test_two_factor(transport, clock):
    transport.add("GET", "/api/profiles/me", json_response({"success": False, "message": "2fa", "data": {"code": "TWOFA_CODE_IS_REQUIRED"}}, 403))
    with pytest.raises(TwoFactorRequiredError):
        await make_http(transport).request("GET", "/api/profiles/me")


async def test_qrator_html_is_bot_check(transport, clock):
    transport.add("GET", "/api/profiles/me", html_response(403))
    with pytest.raises(BotCheckError):
        await make_http(transport).request("GET", "/api/profiles/me")


async def test_cooldown_is_not_retried(transport, clock):
    body = {"success": False, "message": "Попробуйте позже.", "data": {"code": "OFFERS_BUMP_COOLDOWN", "retryAfterSeconds": 14401}}
    transport.add("POST", "/api/offers/bump", json_response(body, 429))
    with pytest.raises(CooldownError) as e:
        await make_http(transport).request("POST", "/api/offers/bump", json={"gameId": 1, "categoryIds": [40]})
    assert e.value.retry_after == 14401
    assert len(transport.calls) == 1


async def test_rate_limit_is_retried_with_pause(transport, clock):
    transport.add("POST", "/api/messages/send",
                  json_response({"success": False, "message": "Too Many"}, 429, {"retry-after": "7"}),
                  json_response({"message": {"id": "m1"}}, 201))
    start = clock.now
    result = await make_http(transport).request("POST", "/api/messages/send", json={"chatId": "c", "content": "x"})
    assert result == {"message": {"id": "m1"}}
    assert len(transport.calls) == 2
    assert clock.now - start >= 7


async def test_rate_limit_gives_up(transport, clock):
    transport.add("GET", "/api/profiles/me", json_response({"success": False, "message": "Too Many"}, 429))
    with pytest.raises(RateLimitError):
        await make_http(transport, rate_limit_retries=3).request("GET", "/api/profiles/me")
    assert len(transport.calls) == 3


async def test_mutation_not_repeated_after_send(transport, clock):
    transport.add("POST", "/api/messages/send", TransportError("timeout", sent=True), json_response({"message": {}}))
    with pytest.raises(NetworkError):
        await make_http(transport).request("POST", "/api/messages/send", json={"chatId": "c", "content": "x"})
    assert len(transport.calls) == 1


async def test_mutation_repeated_when_not_sent(transport, clock):
    transport.add("POST", "/api/messages/send", TransportError("connect", sent=False), json_response({"message": {"id": "m"}}, 201))
    result = await make_http(transport).request("POST", "/api/messages/send", json={"chatId": "c", "content": "x"})
    assert result["message"]["id"] == "m"
    assert len(transport.calls) == 2


async def test_read_repeated_after_network_error(transport, clock):
    transport.add("GET", "/api/profiles/me", TransportError("reset", sent=True), json_response({"user": {"id": 1}}))
    assert (await make_http(transport).request("GET", "/api/profiles/me"))["user"]["id"] == 1


async def test_502_retried_only_for_reads(transport, clock):
    transport.add("GET", "/api/orders/1", html_response(502), json_response({"id": "1"}))
    assert (await make_http(transport).request("GET", "/api/orders/1"))["id"] == "1"

    transport.add("POST", "/api/orders/refund", html_response(502))
    with pytest.raises(Exception) as e:
        await make_http(transport).request("POST", "/api/orders/refund", json={"orderId": "1"})
    assert not isinstance(e.value, BotCheckError)
    assert sum(1 for c in transport.calls if c["path"] == "/api/orders/refund") == 1


async def test_api_error_message(transport, clock):
    transport.add("POST", "/api/messages/send", json_response({"success": False, "message": "chatId must be a UUID"}, 400))
    with pytest.raises(APIError) as e:
        await make_http(transport).request("POST", "/api/messages/send", json={"chatId": "x", "content": "y"})
    assert e.value.status_code == 400 and "UUID" in e.value.message
