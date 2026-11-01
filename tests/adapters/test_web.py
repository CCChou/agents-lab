import httpx
import pytest

from agent.adapters.web import MAX_BYTES, MAX_REDIRECTS, FetchPageTool
from agent.domain.tool import Tool

PUBLIC_IP = "93.184.216.34"


def make_tool(handler, addresses: dict[str, list[str]] | None = None) -> FetchPageTool:
    addresses = addresses or {}
    return FetchPageTool(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolve=lambda host: addresses.get(host, [PUBLIC_IP]),
    )


def html_response(body: str = "<p>Story</p>") -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html"}, text=body)


def test_satisfies_tool_port():
    assert isinstance(make_tool(lambda request: html_response()), Tool)


def test_run_returns_the_page_text_as_untrusted_content():
    tool = make_tool(lambda request: html_response())

    result = tool.run({"url": "https://example.test/a"})

    assert "URL: https://example.test/a" in result
    assert "<untrusted_content>\nStory\n</untrusted_content>" in result


def test_run_reads_from_the_given_offset():
    tool = make_tool(lambda request: html_response("<p>Hello</p>"))

    assert "llo" in tool.run({"url": "https://example.test/a", "offset": 2}).split("\n")[-2]


def test_run_rejects_other_schemes():
    tool = make_tool(lambda request: pytest.fail("should not connect"))

    with pytest.raises(ValueError, match="http"):
        tool.run({"url": "file:///etc/passwd"})


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1", "fd00::1"]
)
def test_run_rejects_hosts_that_resolve_to_private_addresses(address):
    tool = make_tool(
        lambda request: pytest.fail("should not connect"), {"internal.test": [address]}
    )

    with pytest.raises(ValueError, match="public"):
        tool.run({"url": "https://internal.test/"})


def test_run_rejects_a_host_when_any_address_is_private():
    tool = make_tool(
        lambda request: pytest.fail("should not connect"),
        {"mixed.test": [PUBLIC_IP, "10.0.0.5"]},
    )

    with pytest.raises(ValueError, match="public"):
        tool.run({"url": "https://mixed.test/"})


def test_run_rejects_a_host_that_does_not_resolve():
    tool = make_tool(lambda request: pytest.fail("should not connect"), {"gone.test": []})

    with pytest.raises(ValueError, match="public"):
        tool.run({"url": "https://gone.test/"})


def test_run_follows_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "/new"})
        return html_response()

    assert "Story" in make_tool(handler).run({"url": "https://example.test/old"})


def test_run_rejects_a_redirect_to_a_private_address():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "example.test"
        return httpx.Response(302, headers={"location": "http://internal.test/"})

    tool = make_tool(handler, {"internal.test": ["10.0.0.5"]})

    with pytest.raises(ValueError, match="public"):
        tool.run({"url": "https://example.test/"})


def test_run_stops_after_too_many_redirects():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"location": "/loop"})

    with pytest.raises(ValueError, match="redirects"):
        make_tool(handler).run({"url": "https://example.test/loop"})

    assert len(requests) == MAX_REDIRECTS + 1


def test_run_raises_on_http_errors():
    tool = make_tool(lambda request: httpx.Response(403))

    with pytest.raises(httpx.HTTPStatusError):
        tool.run({"url": "https://example.test/"})


def test_run_rejects_non_text_responses():
    tool = make_tool(
        lambda request: httpx.Response(
            200, headers={"content-type": "application/pdf"}, content=b"%PDF"
        )
    )

    with pytest.raises(ValueError, match="application/pdf"):
        tool.run({"url": "https://example.test/a.pdf"})


def test_run_reads_at_most_max_bytes():
    body = "<p>" + "a" * (MAX_BYTES * 2) + "</p>"
    tool = make_tool(lambda request: html_response(body))

    result = tool.run({"url": "https://example.test/"})

    assert f"of {MAX_BYTES}" in result or f"of {MAX_BYTES - 3}" in result


def test_read_text_returns_the_whole_page_text():
    tool = make_tool(lambda request: html_response("<p>Hello</p>"))

    assert tool.read_text("https://example.test/") == "Hello"


def test_read_text_applies_the_same_address_checks():
    tool = make_tool(
        lambda request: pytest.fail("should not connect"), {"internal.test": ["10.0.0.5"]}
    )

    with pytest.raises(ValueError, match="public"):
        tool.read_text("https://internal.test/")
