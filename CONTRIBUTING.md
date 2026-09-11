# Contributing to SoAI

Thank you for wanting to help. Please read this before opening a pull request, because SoAI does not work the way most repositories on GitHub do.

## Code contributions are not accepted

**Pull requests are closed without review and are never merged.** This is not a judgement about your code, and it is not a reflection of how the report was written. It is a structural decision about who owns SoAI's source.

`LICENSE.md` section 10 states that outside code contributions are not accepted unless and until a contribution policy and rights process is published. This document is not that process. No such process is currently open or planned.

The reason is a promise made to every user. Each numbered official release of SoAI Core converts to the MIT License exactly four years after its first public distribution, on the immutable schedule in `CHANGE-DATES.md`. That promise is only deliverable if a single party holds the rights to every line of first-party source. Merging outside code — even a one-line fix, even with the best intent — would put source into SoAI that the Licensor cannot relicense, and the Change Date commitment would quietly become undeliverable. Declining contributions is how that commitment stays real.

So please do not spend your time on a patch for this repository. If you have forked SoAI on GitHub, `LICENSE.md` section 5 explains what that fork does and does not permit.

## What is genuinely welcome

**Bug reports.** The most useful thing you can send. Include the SoAI version, platform, what you did, what happened, and what you expected. A reliable reproduction is worth more than a proposed fix.

**Feature requests and design feedback.** Describe the problem you are trying to solve and the outcome you want, rather than the implementation. Real use cases shape the roadmap.

**Documentation corrections.** Wrong, stale, or confusing documentation is a defect. Point at the exact place and say what it should say.

**Security reports.** Do not open a public issue. Follow `SECURITY.md`, which sets out the single point of contact, the coordinated-disclosure timelines, and the declared support period.

**Plugins.** This is the part of SoAI built for you to extend. `LICENSE.md` section 7.1 grants anyone — a person or a company, with or without a paid grant — a perpetual, royalty-free right to study `plugin_sdk`, build a plugin against it, and use, publish, sell, and distribute that plugin under any license you choose. Your plugin stays yours; the Licensor claims nothing in it. The bundled `.soaiplugin` packages are MIT-licensed precisely so you can read them and start from them. Build and publish plugins freely — that ecosystem is yours, not this repository.

**Reviews, benchmarks, and teaching.** `LICENSE.md` section 3.1 lets you install and run SoAI Core to test it, measure it, compare it against other software, teach with it, and publish what you find, including unfavourable findings, with no request, registration, approval, embargo, or entitlement required.

## About code in issues

Please describe the problem rather than supply a patch. `LICENSE.md` section 5 permits you to publish diffs and limited source excerpts needed to discuss a fix, so a short snippet that makes a bug clearer is fine and welcome. Keep it to the minimum the explanation needs, and understand that including it is not a request to merge it and creates no claim to the resulting code. Issue reports and suggestions transfer no ownership and create no right to have code merged.

## Conduct

Be straightforward and civil. Technical disagreement is fine and useful; personal attacks, harassment, and spam are not, and will be moderated. Reports of unfavourable behaviour by the project itself are also welcome — say so plainly in an issue or at `info@soai.to`.
