# Native HTTP(S) clients — 0.26 preview

`weave "stdlib/http.ramos"` provides synchronous GET/POST requests that capture response
bytes. Ramos calls **libcurl on Linux** and the **system WinHTTP library on
Windows**, directly from the native executable. It does not spawn curl, Python,
a shell, or a helper executable. TLS is supplied by those native libraries;
Ramos does not implement its own cryptography.

Linux networking executables need `libcurl.so.4` and the x64 ELF loader. The
compiler automatically adds the HTTP imports when it emits the HTTP intrinsic;
no `--net` flag is required. CLI programs without HTTP remain static. GTK is
still opt-in with `--gui`; combining HTTP and GUI loads both libraries. Windows
loads WinHTTP from System32 lazily, without another DLL to distribute.

## API

```ramos
struct HttpResponse { code: int64, status: int64, body: bytes }
```

- `http_get(url: string, headers: [string], timeout_ms: int64) -> HttpResponse`
- `http_post(url: string, headers: [string], body: bytes, timeout_ms: int64) -> HttpResponse`
- `http_request(method: string, url: string, headers: [string], body: bytes, timeout_ms: int64) -> HttpResponse`

`method` must be `s"GET"` or `s"POST"`. GET requires an empty body. POST accepts
arbitrary bytes, including NUL and UTF-8 JSON. Headers are individual ASCII
`Name: value` lines with nonempty token names and nonempty values. Do not add
CR/LF terminators. A response body is a fresh mutable byte buffer.

`status == 0` means a complete HTTP response was received. `code` is its HTTP
status: a 401, 429 or 500 is an HTTP result with its response body, not a transport
failure. A negative `status` means the request failed; `code` is zero and the
body is empty, including after an interrupted or oversized response. Treat the
returned record's status as authoritative: library validation can return before
calling the intrinsic and therefore does not change `io_error()`.

| Status | Meaning |
| --- | --- |
| -22 | Invalid method, URL, header, timeout or private packet |
| -7 | Request metadata/header count exceeds the library limit |
| -27 | Response body exceeds capacity |
| -13 | TLS handshake, certificate/trust-store or hostname verification failure |
| -110 | Network timeout |
| -113 | Hostname resolution failure |
| -111 | Connection failure |
| -38 | Required native API unavailable |
| -5 | Other native transport failure |

Limits are explicit: URL at most 8,192 ASCII bytes; at most 64 headers; total
packed request metadata at most 32,768 bytes; POST body at most the existing
1 MiB buffer limit; response body at most **1,048,568 bytes** (eight metadata
bytes share the output buffer). Timeouts must be 1..120,000 milliseconds.

URLs must start with lowercase `http://` or `https://`, have a nonempty authority,
and contain ASCII bytes without spaces, backslashes, fragments or embedded
credentials. Use percent encoding for non-ASCII paths and punycode for DNS names.
Only HTTP(S) protocols are enabled. Requests are direct: automatic proxy lookup
and environment proxy variables are not used. Redirects are returned to the
caller, never followed automatically. Response headers, raw sockets, servers,
async requests and streaming/SSE parsing are not provided by this milestone.

## TLS and timeout contracts

HTTPS verifies the certificate chain and the URL hostname, with TLS 1.2 or newer.
There is no certificate-disable option. Linux uses libcurl's system trust store;
if `SSL_CERT_FILE` is nonempty, it explicitly selects a PEM trust bundle while
verification stays enabled. Windows uses the OS trust store. The client does not
attempt automatic Windows authentication; explicit Authorization headers work.

The timeout bounds the network transfer. Linux uses libcurl's transfer timer;
Windows uses private native completion callbacks and an event wait with the
remaining transfer budget. DNS/connect/send/read stages share that budget.
On timeout, Windows cancels the request and waits for the final native handle
closing callback before releasing buffers. Cancellation cleanup and the final
response copy can extend total call duration; this is not a strict wall-clock
return guarantee. The public API remains synchronous and does not provide
background GUI work.

Native contracts: [libcurl hostname checking](https://curl.se/libcurl/c/CURLOPT_SSL_VERIFYHOST.html),
[libcurl transfer timeout](https://curl.se/libcurl/c/CURLOPT_TIMEOUT_MS.html),
[WinHTTP requests](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpopenrequest)
and [WinHTTP TLS/redirect options](https://learn.microsoft.com/en-us/windows/win32/winhttp/option-flags).

## A JSON/API client in Ramos

The complete [api_post example](../examples/api_post.ramos) reads a JSON request
file, optionally adds `RAMOS_API_TOKEN` as a Bearer token, captures the HTTP(S)
response, writes its bytes to stdout and exits nonzero on transport or non-2xx
results. It does not print the token or place it on the command line.

```sh
./ramos build examples/api_post.ramos -o api-post
./api-post https://your-api.example/endpoint request.json
# Or compile and run directly:
./ramos run examples/api_post.ramos -- https://your-api.example/endpoint request.json
```

On Windows, use the same source and compiler/library bundle:

```powershell
.\ramos.exe build .\examples\api_post.ramos -o .\my-api-post.exe
.\my-api-post.exe https://your-api.example/endpoint .\request.json
```

Supply a real endpoint and its required JSON yourself. For a non-streaming LLM
API, put its model/messages and other required fields in that file. This is a
native transport client, not an SDK, JSON parser or complete autonomous agent.
No live provider or paid LLM call is part of the automated tests.

## Verification scope

Controlled loopback fixtures exercise GET/POST, binary and Unicode bodies,
request headers/query strings, chunked responses, empty/401/302 results, no
redirect following, connection refusal/timeouts, response limits and repeated
requests/collection. TLS fixtures use a temporary trusted CA to prove success,
then reject hostname mismatch and an untrusted certificate before any HTTP
request is sent. Linux selects a per-process test trust bundle; native Windows
installs its unique fixture CA in the disposable CI machine's Root store and
removes that exact certificate afterward. Those Windows TLS tests require an
elevated, isolated test host; application requests themselves do not require
administrator access. Python/OpenSSL are test tooling only.

The retained seed skips the new library/intrinsic tests. Windows TLS acceptance
requires native Windows; Wine is not a substitute for that trust-store proof.
GUI scaling retains its separate [preview acceptance](gui-scaling.md).
