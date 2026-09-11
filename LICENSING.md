# SoAI licensing overview

This file is explanatory. The exact accepted operative documents and signed
entitlement control.

## Products and documents

SoAI Core is the first-party material published in this repository and is
governed by `LICENSE.md`. SoAI OS is a separate product governed by the SoAI OS
Source-Available License, which ships only inside SoAI OS artifacts and is published for everyone at
`https://soai.to/downloads/soai-os-LICENSE.md`. Delivering both together does not
merge or relicense them. Every operative document is published at
`https://soai.to/downloads/`, so a Core artifact never has to carry the OS terms
for you to read them.

Two first-party components are a separate case. The bundled `.soaiplugin`
packages in `plugins/` and the SoAI Connect Android client published in its separate repository
are licensed under the MIT License in `licenses/MIT.txt` and are excluded from
the Core Licensed Work by `LICENSE.md` section 7. They may be freely inspected,
copied, modified, and redistributed, including as a starting point for your own
plugins or your own client. That permissive grant covers those first-party
sources only. It does not cover `plugin_sdk` or any other Core material, carries
no SoAI trademark right, and does not by itself permit running SoAI Core, which
still requires personal, evaluation, or commercial rights.

Writing plugins is separately and expressly permitted. `LICENSE.md` section 7.1
grants anyone — a person or a company, with or without a paid grant — a
perpetual, royalty-free right to study `plugin_sdk`, build a plugin against it,
and use, publish, sell, and distribute that plugin under whatever license they
choose. The plugin stays theirs; the Licensor claims nothing in it. A plugin must
not ship `plugin_sdk` or other Core material inside it, because it takes the SDK
from the SoAI installation that runs it, and running SoAI to develop, test, or
operate the plugin still needs personal, evaluation, or commercial rights.

The licensing documents are:

- `LICENSE.md` — SoAI Core Source-Available License 1.0;
- `CHANGE-DATES.md` — immutable Core release/change-date schedule;
- `ORGANIZATION-EVALUATION-TERMS.md` — Core and converted OS evaluation terms;
- `COMMERCIAL-LICENSE.md` — standard annual commercial terms;
- `COMMERCIAL-SUPPORT-TERMS.md` — standard commercial support;
- SoAI OS Source-Available License 1.0; and
- Personal SoAI OS Purchase Terms — personal USD 99 purchase.

The last two ship only inside SoAI OS artifacts. Core artifacts carry the five
Core documents and reference the OS terms by their published address.

`PRIVACY.md` is explanatory alongside this file. It describes what the software
does with your data and what it sends: licensing requests carry deployment and
entitlement identifiers and your accepted document fingerprints, never prompts,
model inputs or outputs, files, credentials, or usage statistics.

## Personal use

SoAI Core is free for one natural person's private personal use, without a paid
key or deployment-slot limit. Employer tasks, client work, freelancing, a trade or
business, and any organization use require evaluation or commercial rights.

Personal SoAI OS costs USD 99 once. It grants one named natural person perpetual
personal use on up to three active deployments and every update generally released
for the same SoAI OS product without another software-license fee. It includes no
organization use, redistribution, OEM, white-label, or professional support.

## Organization evaluation

An identified organization may receive one general 30-day evaluation: either one
standalone Core deployment, or one purchased and activated personal OS deployment
converted in place for that organization. There is no general Core + OS evaluation
or separately downloadable free OS evaluation. The Core term begins at first
activation; the OS term begins at committed conversion.

The converted OS deployment does not consume a personal slot. It may revert only
after company use ends, company data is handled lawfully, and a personal slot is
available. Expiry restricts SoAI application functions but preserves licensing,
status, logs, data access, backup/export, recovery, and limited safe repair; it
never locks Debian or customer data.

## Standard annual commercial offers

- Core Commercial: USD 499/year, three production plus three non-production Core
  deployments, one professional-support hour per term.
- SoAI OS Commercial: USD 799/year, three production plus three non-production OS
  deployments including their Core components, two support hours per term.
- Core + OS Commercial: USD 999/year, standalone Core and OS sharing three
  production plus three non-production deployments total, four support hours per
  term.

Standard commercial use includes internal business use, hosted OpenAI-compatible
and Anthropic-compatible APIs, MCP services, inference platforms, hosted SoAI WebUI
access retaining SoAI identity, SaaS, managed services, agents, chatbots, and
customer-facing apps. It does not include software redistribution, independent
customer installations, downloadable embedding, sublicensing, OEM distribution, or
white-labeling.

Perpetual commercial, OEM, product-building, redistribution, expanded capacity,
and broader rights require a separately signed private agreement.

## Offline validity, updates, and Change Dates

Activated perpetual personal OS works locally without recurring checks. Commercial
entitlements work offline through their written paid term. A narrowly bounded,
non-stackable continuity record of no more than 30 days may be issued only after
timely renewal payment is confirmed but normal term delivery fails.

Personal OS purchasers receive generally released updates for the same product.
Commercial customers receive updates for their paid scope during the active term.
Only signed numbered official releases are eligible for self-update.

Each numbered Core Official Release becomes available under MIT exactly four years
after first official public distribution. A Core Change Date never converts SoAI
OS or a later Core release early.

## Seller, support, and contact

Roberto Martini is the individual software owner, licensor, supplier, and support
provider. Paddle is the authorized reseller and merchant of record for transactions
processed by Paddle.

Licensing, purchasing, and commercial enquiries: `sales@soai.to`. Support under a
paid term: `support@soai.to`. Security reports: `security@soai.to`. Privacy and
data-protection requests: `privacy@soai.to`. General enquiries and formal notices
under the operative licenses: `info@soai.to`. Current public contacts are published
at `https://soai.to/legal-notices/`, which is the contact of record for notices.
