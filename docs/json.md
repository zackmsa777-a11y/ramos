# JSON library (development source)

These libraries are on the development branch after the 0.26.0 HTTP preview.
The published 0.26.0 archive does not contain them. They use the unchanged
0.26 compiler; build the examples from a current source checkout.

```ramos
weave "../stdlib/json.ramos"
fn main() {
    let doc = json_parse("{\"name\":\"مرحبا 🌍\",\"count\":1e400}")
    if doc.status != 0 {
        print(doc.error_at)
        exit(1)
    }
    print(json_text(doc, json_get(doc, doc.root, s"name")))
    print(json_raw(doc, json_get(doc, doc.root, s"count")))
    let compact = json_encode(doc)
    if compact.status != 0 { exit(1) }
    print(compact.text)
}
```

`json_parse(bytes)` owns a copy of its input and returns `JsonDocument`.
Check `status` before reading the root. Status 0 succeeds; -22 means invalid
JSON or UTF-8; -27 means a documented limit. `error_at` is the zero-based byte
offset where validation stopped, including EOF, or -1 on success. Failed roots
are -1. Input mutation cannot change the parsed document or raw number text.
Document fields and parser/writer helpers are implementation details: callers
must not mutate them. Aliases share the same document. Normal managed collection
reclaims it when no longer reachable; the existing 16 MiB live-heap cap applies.

Node IDs are integers local to a document; -1 is absent. `json_kind(doc, node)`
returns 0 for an invalid/absent node or failed document, otherwise:

| Kind | Value |
| --- | --- |
| 1 | null |
| 2 | boolean |
| 3 | number |
| 4 | string |
| 5 | array |
| 6 | object |

`json_get(doc, object, key)` returns a member node or -1. Duplicate names are
accepted and lookup returns the last occurrence, matching common JSON parsers.
`json_at(doc, array, index)` returns an element or -1. Wrong container kinds
also return -1. `json_size` counts direct array elements or object members,
including duplicate names; other kinds return 0. `json_text` returns a decoded
string or an empty string for other kinds: check the kind to distinguish an
empty string from a missing or differently typed value.

`json_raw` returns the exact JSON spelling of a node, including quotes around
strings. Numbers stay exact decimal text: large integers and `1e400` are valid
JSON and do not require binary64 conversion. Convert numbers separately using
the documented integer/float APIs when their range fits your application.

`json_encode(doc)` returns `JsonText(text, status)` with compact JSON and
decoded strings escaped again. It preserves member order, duplicate members
and exact number spelling. `json_quote(string)` produces one safely quoted
JSON string with the same result type. NUL and control characters are escaped;
UTF-8 text is preserved. Build new objects/arrays from these quoted strings,
integer text and a `TextBuilder`; no dynamic JSON mutation API is supplied.
The encoder is not a generic serializer for arbitrary Ramos structs.

Strict syntax rejects comments, trailing commas, leading-zero numbers,
NaN/Infinity, a leading BOM, malformed escapes, unpaired UTF-16 surrogates and
invalid UTF-8. Only space, tab, CR and LF are JSON whitespace. Valid surrogate
pairs decode to one Unicode scalar. `json_validate_utf8(bytes)` separately
returns `JsonCheck(status, error_at)` without parsing JSON; use it before
converting an untrusted UTF-8 file to `string`.

Limits: input and encoded output each at most 1,048,576 bytes; 4,096 value
nodes (object keys do not consume a node); a scalar can be nested inside at most
64 containers. The output limit can reject a parsed document when escaping
expands its strings. Size errors return empty output. Allocation exhaustion
still uses the checked runtime error. No streaming parser is provided.

The tests compare nested and randomized round trips with Python's independent
JSON parser, preserve out-of-range decimal spelling, reject malformed Unicode,
exercise exact bounds, lookup/snapshot behavior and repeated collection. The
agent example uses this parser on actual native HTTP(S) responses.
