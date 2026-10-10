# GitHub language recognition

Ramos has a native compiler written in `.ramos`, with a verified self-hosting
fixed point. GitHub's Languages sidebar is computed by Linguist and is separate
from the language in which the active compiler is implemented.

As checked on 2026-10-10, Ramos is absent from
[Linguist's language registry](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml).
GitHub cannot display a new `Ramos` category just because we set a repository
attribute. Linguist explicitly says that
[unregistered languages remain excluded from statistics](https://github.com/github-linguist/linguist/blob/main/docs/overrides.md#detectable),
even with `linguist-language` and `linguist-detectable` overrides.

Upstream recognition requires a language entry, an appropriate highlighting
grammar, representative code samples, and sufficiently widespread public use.
The current [contribution policy](https://github.com/github-linguist/linguist/blob/main/CONTRIBUTING.md#language-extension-and-filename-usage-requirements)
requires at least 2,000 indexed files for an extension normally used more than
once per repository, distributed across independent projects rather than
concentrated under the language's author. Creating artificial duplicate files
would not satisfy that policy.

The repository README identifies the actual compiler as Ramos and links to its
source and bootstrap proof. The original assembly bootstrap and Python tests
remain visible under their real languages. No files are disguised or relabeled
to manufacture a "100% Ramos" language bar. The sidebar can name Ramos once
GitHub accepts and deploys Linguist support; its exact percentage will also
reflect other source files retained in the repository.

## Registration implementation (2026-10-10)

The technical registration is implemented on the [`add-ramos` branch of the
Ramos owner's Linguist fork](https://github.com/zackmsa777-a11y/linguist/tree/add-ramos):

- A programming-language entry for `.ramos`, scope `source.ramos`, an upstream
  script-generated language ID, and an initial teal color (`#16A085`). The color
  is an initial visual choice, not a claim of established community branding.
- An MIT-licensed [TextMate grammar](https://github.com/zackmsa777-a11y/language-ramos),
  registered through Linguist's own `script/add-grammar` with a pinned submodule,
  generated grammar metadata, documentation and license cache.
- A newly authored, MIT-licensed
  [stdin statistics tool](https://github.com/zackmsa777-a11y/language-ramos/blob/main/examples/line-stats.ramos)
  as a runnable sample, plus an extension/classification regression test.

The registration passed **2,052 Linguist tests / 41,114 assertions** with no
failures. The grammar passed 17 TextMate scope assertions, runnable-sample
tokenization and upstream grammar compilation; editor package CI is green.
See [recorded verification](linguist-verification.json).

This fork classifies the actual `compiler/ramos.ramos` file as Ramos. It does not
change the registry running on GitHub.com. See [the submission checklist](linguist-submission.md).

Draft [upstream PR #8264](https://github.com/github-linguist/linguist/pull/8264) was
opened at the owner's explicit request and then closed when that request was
cancelled. Ramos has not been accepted upstream. Besides the contribution policy,
[Linguist's AGENTS.md](https://github.com/github-linguist/linguist/blob/main/AGENTS.md)
explicitly requires the usage evidence, sample licensing and passing CI, and says:
"Do not open a PR if any of the above conditions are not met".
The widespread-usage requirement remains unmet. An authenticated legacy GitHub
code-search query for `extension:ramos` returned zero indexed results on this
date; that API has indexing limitations and does not mean the Ramos sources in
this repository do not exist. No evidence of 2,000 qualifying independent files
was found, and the registration is not presented as eligible for upstream acceptance.

## Highlighting available now

The [VS Code extension release](https://github.com/zackmsa777-a11y/language-ramos/releases/tag/v0.9.0)
includes `language-ramos.vsix`. Use **Extensions: Install from VSIX...**, or:

```sh
code --install-extension language-ramos.vsix
```

This gives `.ramos` files a local Ramos language mode, highlighting, comment
toggling and bracket matching. It is not a compiler or language server and does
not change GitHub's language statistics. Its grammar covers the current 0.9
syntax, including comments, short-circuit booleans and the new input/text intrinsics.
