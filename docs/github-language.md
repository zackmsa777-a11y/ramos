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
