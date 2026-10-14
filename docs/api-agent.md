# A bounded Ramos API agent (development source)

`examples/api_agent.ramos` is a small native CLI tool loop using the new
[JSON library](json.md) and the [0.26 HTTP(S) client](http.md). It follows the
non-streaming Chat Completions text/function-call format described in the
[official OpenAI function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling).
The user supplies a compatible endpoint and a model supporting the requested
tool schema. This is a protocol subset, not a complete provider SDK or a coding
agent. Other API formats, reasoning extensions, streaming and multiple tool
calls per response need separate implementations.

From a current source checkout on Windows, keep `stdlib/` beside `examples/`:

```powershell
.\ramos.exe build .\examples\api_agent.ramos -o .\api-agent.exe
# Write prompt.txt as UTF-8 without a BOM using your editor.
# Set RAMOS_API_TOKEN in your environment if your provider requires a token.
.\api-agent.exe https://YOUR_HOST/v1/chat/completions YOUR_MODEL .\prompt.txt
```

On Linux, install libcurl.so.4, then:

```sh
./ramos build examples/api_agent.ramos -o build/api-agent
./build/api-agent https://YOUR_HOST/v1/chat/completions YOUR_MODEL prompt.txt
```

The executable makes native HTTP requests directly: Linux libcurl and Windows
WinHTTP. Python is used for controlled acceptance tests only. Use HTTPS for
remote endpoints; plain HTTP is useful for a local server. The token is read
from `RAMOS_API_TOKEN`, must contain visible ASCII, and is sent as an
Authorization header. It is not printed. HTTP failures report the status code
without dumping the provider body. Prompt content is sent to the chosen endpoint.
Calling a real provider can consume credits; the tests never do so.

The loop sends the UTF-8 prompt as a user message. If the assistant requests
`text_stats`, Ramos validates its JSON arguments, computes Unicode-scalar and
UTF-8-byte counts, returns the result with the same tool-call ID and sends the
updated conversation. A complete final text reply goes to stdout with a newline.
The only accepted arguments are an object with exactly one string member
`text`. Unknown tools, malformed arguments, unexpected roles, multiple calls,
incomplete replies and invalid JSON stop with exit 1. The model cannot select
files or commands: the example supplies only the text-statistics function.

The example deliberately stays bounded: at most eight HTTP requests including
the final answer, 30,000 ms request timeout, a 256 KiB encoded conversation,
one choice and at most one tool per response. JSON and HTTP size limits still
apply. Missing/invalid usage exits 2; `--help` exits 0. No retries, persistence,
API response headers, cancellation UI or general tool framework are provided.
Requests block, so do not put this loop on a GUI event thread.

Acceptance uses a controlled local HTTPS server and temporary trusted CA to
exercise authentication, Unicode, the exact outgoing tool-result schema and
final response. Separate cases test malformed replies, unknown tools, invalid
arguments/prompts/tokens, the eight-request stop and the conversation cap.
This demonstrates orchestration; it does not measure a real model's quality or
establish compatibility with every provider/model.
