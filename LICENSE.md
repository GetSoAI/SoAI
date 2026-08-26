# SoAI Source-Available License 1.0

SPDX-License-Identifier: `LicenseRef-SoAI-Source-1.0`

Document ID: `soai_core_license`

Version 1.0 — effective 22 August 2026

Copyright © 2024–2026 Roberto Martini. All rights reserved except as expressly
granted by this License.

## 1. Definitions

**Licensor** means Roberto Martini, an individual in Italy.

**SoAI Core** and **Licensed Work** mean the first-party SoAI source code,
launchers, assets, and documentation published as SoAI Core and identifying this
License as governing them. SoAI OS is a separately distributed product and is
not part of this Licensed Work. MIT Components are licensed separately under
section 7 and are not part of this Licensed Work.

**Bundled Plugins** means the first-party `.soaiplugin` packages the Licensor
distributes with SoAI Core, together with their first-party source members. It
does not include `plugin_sdk`, any other backend or frontend material, or any
third-party inference engine, provider, model, or dependency a plugin installs,
launches, or communicates with.

**SoAI Connect** means the first-party Android companion client source published
in its separate public repository and the application package built from it. It does not include
any other backend, frontend, or SoAI OS material, or any third-party Android
library it depends on.

**MIT Components** means Bundled Plugins and SoAI Connect together.

**Plugin SDK** means the `plugin_sdk` package, the public documented boundary
through which a plugin interacts with SoAI. The Plugin SDK is part of the
Licensed Work.

**Your Plugin** means a plugin package You develop that runs inside a SoAI
Deployment and interacts with SoAI only through the Plugin SDK. It does not
include the Plugin SDK itself or any other part of the Licensed Work.

**You** means the natural person or organization exercising rights under this
License.

**Personal Use** means use by one natural person acting privately on their own
behalf. It includes learning, experimentation, research, hobbies, personal
projects, and professional learning that is not an employer task, client work,
production work, processing of employer or client data, operation of an
organization's systems, or delivery of outputs for an organization. Personal Use
does not include use for the purposes of freelancing, a trade, business, craft,
profession, or paid service, or production use primarily intended to generate
revenue. Incidental donations or advertising on an otherwise genuine personal
project do not alone make that project organizational use.

**Organization** means any company, sole proprietor acting as a business,
partnership, nonprofit, school, university, public body, government body,
employer, client, or other legal or collective entity.

**Deployment** means one independently managed SoAI control plane with one
licensing identity, regardless of users, GPUs, models, inference engines,
workers, requests, or downstream workloads. Replicas count as one Deployment
only if they are a single logical high-availability control plane, share
configuration and one entitlement, and cannot operate independently. A
separately operable control plane or traffic-serving standby is another
Deployment. Powered-off backups and cold copies that serve no traffic and
cannot operate concurrently are not Deployments.

**Official Release** means a numbered SoAI Core version that the Licensor
publishes as an official GitHub release and identifies by an immutable tag,
release commit, and signed release manifest. Arbitrary commits are not Official
Releases.

**Change Date** means the immutable date recorded for an Official Release in
`CHANGE-DATES.md`, exactly four years after its first official public
distribution.

**Change License** means the MIT License in `licenses/MIT.txt`.

## 2. Personal grant

Subject to this License, the Licensor grants You, if You are a natural person, a
worldwide, non-exclusive, non-transferable, royalty-free, perpetual right to
inspect, copy, run, and privately modify the Licensed Work for Personal Use.

You may run SoAI Core on Your own devices and private infrastructure. Members of
Your household and private household guests may use those installations, but
receive no transferable license of their own. SoAI Core Personal Use is free of
charge, requires no paid product key, and has no Deployment limit.

This grant covers every Official Release of SoAI Core without another
software-license charge, including major and minor versions. It promises no
particular update, feature, version, release schedule, support period, or
indefinite continued development, and does not automatically extend to a
genuinely separate successor product. A rename may not be used merely to evade
this grant. Mandatory consumer conformity, remedy, and necessary-update rights
remain unaffected.

This grant does not authorize deployment for an employer, client, business,
nonprofit, school, government body, or any other Organization.

## 3. Organization evaluation

Except as stated in section 3.1 and section 7.1, this License alone grants no
Organization a right to use SoAI Core. An identified Organization may use one
SoAI Core Deployment for one genuine internal 30-day evaluation only under an
entitlement issued after acceptance of the exact
`ORGANIZATION-EVALUATION-TERMS.md` version recorded in that entitlement.

The evaluation begins on the first successful activation, not reservation or
download. It is not a continuing production license and is not repeatedly
renewable as a right. The evaluation terms govern that use.

### 3.1 Review, press, benchmarking, and teaching

Independent examination for publication is not organizational production use. A
journalist, reviewer, publication, benchmarker, researcher, educator, or student
may install and run SoAI Core without an entitlement, for as long as reasonably
needed, in order to test it, measure it, compare it against other software, teach
with it, or publish what they find, including unfavourable findings. This covers
both the individual's own Deployment and a Deployment their employer or
institution operates for that purpose.

This permission needs no request, approval, registration, or notice, and the
Licensor will not condition it on prior review of what is published, on a
positive result, or on any embargo the publisher has not separately agreed. It
does not authorize running the organization's ordinary operations, serving its
customers, or processing business data beyond what the examination itself
requires, and it grants no redistribution, sublicensing, or SoAI OS right.

## 4. Commercial use

All Organization use outside a valid evaluation requires an active commercial
grant. The standard annual grant is governed by `COMMERCIAL-LICENSE.md`, the
applicable accepted order, and its signed entitlement. A separately signed private
agreement may grant different rights. Payment, source access, possession of an
installer, or technical access to activation does not create an unwritten right.

## 5. Restrictions

Except where an applicable commercial agreement expressly permits it, You must
not:

1. distribute substantially complete SoAI source or binary copies, installers,
   appliance images, or forks to a third party;
2. sublicense, resell, provide OEM delivery, embed SoAI in a downloadable or
   on-premises third-party product, or transfer an independently operated SoAI
   control plane to an unlicensed customer;
3. white-label SoAI, remove or obscure required copyright, license, attribution,
   legal, or SoAI branding notices, or present SoAI as software created by You;
4. represent a modified version as an official SoAI release or as endorsed by the
   Licensor;
5. bypass, falsify, attack, or interfere with licensing, entitlement, capacity,
   attribution, or notice mechanisms; or
6. cause or assist another person to exceed the rights applicable to them.

You may publish patch files, diffs, issue examples, and limited source excerpts
reasonably needed to discuss or propose a fix.

Where the Licensor publishes SoAI Core in a public GitHub repository, GitHub's own
platform terms allow any GitHub user to view and fork that repository on GitHub,
and this License does not attempt to withdraw that platform right. In plain terms:
You may fork the repository on GitHub. That fork gives You no right to run SoAI
Core beyond the grant You already hold under this License, and no right to publish
builds or installers, to distribute substantially complete copies outside GitHub,
or to offer the fork as a product or service, before the applicable Change Date.

### 5.1 Trade control compliance

You must comply with the export control and economic sanctions law that applies to
You, including European Union and Italian restrictive measures. You must not use,
receive, export, re-export, or make SoAI available in or to a territory,
government, entity, or person covered by such a measure, and You confirm that You
are not such a person and are not acting on behalf of one. The Licensor may refuse,
suspend, or terminate an entitlement where continuing would breach such a measure.
This obligation survives termination.

## 6. Modifications, data, and outputs

Private modifications are permitted only within Your active grant. You own Your
independent code, inputs, data, configurations, and outputs to the extent provided
by applicable law and third-party terms. The Licensor acquires no ownership merely
because material is processed by SoAI. You remain responsible for security,
backups, providers, models, plugins, validation of outputs, and lawful operation.

## 7. MIT Components

MIT Components are licensed under the MIT License in `licenses/MIT.txt`, and
those MIT terms alone govern them. Each `.soaiplugin` package carries that text
at `LICENSES/LICENSE_SOAIPLUGIN.txt`; SoAI Connect carries the same license in
its separate source repository and reproduces it in the application's licenses screen.

This permissive grant stands apart from Your rights in the Licensed Work. It lets
You inspect, copy, modify, and redistribute MIT Components, including as a basis
for Your own plugins or Your own client. It grants no right to run, copy, or
distribute SoAI Core itself. Operating a plugin inside a SoAI Deployment, or
connecting a client to one, still requires rights applicable to that Deployment.

The MIT grant conveys no right in the SoAI name, logos, or product identity,
which remain reserved under section 10. Third-party inference engines, providers,
models, Android libraries, and other dependencies that an MIT Component installs,
launches, embeds, or communicates with remain governed by their own licenses and
notices. Each plugin package records an applicable managed-backend license at
`LICENSES/LICENSE_MANAGED_BACKEND.txt`, and SoAI Connect records its embedded
components in the third-party notice published in its separate source repository
and in its licenses screen.

### 7.1 Plugin development

The Licensor grants You a worldwide, non-exclusive, royalty-free, perpetual right
to read and study the Plugin SDK, to develop Your Plugin against it, and to use,
publish, sell, and distribute Your Plugin to anyone, under any license terms You
choose. This right does not depend on which grant in sections 2 to 4 You hold,
and it is available to a natural person and to an Organization alike.

Your Plugin may reproduce the Plugin SDK's interface names, signatures, types,
constants, and documented behaviour to the extent needed to interoperate with it,
and may be published in source or binary form, commercially or free of charge.
You must not distribute the Plugin SDK itself, or any other part of the Licensed
Work, inside or alongside Your Plugin. A plugin obtains the Plugin SDK from the
SoAI installation that runs it.

Your Plugin is Yours. The Licensor claims no ownership in it, no license to it,
and no right to distribute it, and section 5 does not restrict it.

This grant authorizes no other use of the Licensed Work. Running SoAI Core to
develop or test Your Plugin, and running Your Plugin in a Deployment, each still
require rights applicable to that Deployment under sections 2 to 4. The grant
conveys no right in the SoAI name, logos, or product identity beyond the truthful
nominative use permitted by section 10, and You remain responsible for Your
Plugin, including its security, its dependencies, and its conformity with law.

## 8. Third-party materials

This License applies only to first-party materials the Licensor owns or may
license. Dependencies, operating-system packages, models, providers, managed
backends, and third-party plugins remain governed by their own licenses and
notices. Nothing here narrows rights granted directly by those terms.

## 9. Change Date

On and after an Official Release's Change Date, that exact SoAI Core version is
also available under the Change License. The Change Date cannot be postponed.
Conversion of one version does not convert a later version early and never
converts any SoAI OS material.

The Change License grants no trademark right and does not authorize a modified
copy to be represented as official or endorsed. The authoritative signed release
manifest and `CHANGE-DATES.md` identify each Official Release and its date.

## 10. Ownership, marks, and patents

The Licensed Work is licensed, not sold. The Licensor retains every right not
expressly granted. The SoAI name, logos, and product identity are reserved. You
may use them only for truthful nominative references such as compatibility or
that a service is powered by SoAI, without implying endorsement.

For the scope and duration of a valid grant, the Licensor grants a limited,
worldwide, non-exclusive patent license under patent claims the Licensor controls
that are necessarily infringed by authorized use of the applicable unmodified
Licensed Work or permitted modifications. This does not state that any SoAI
patent exists, warrant non-infringement, or grant rights under third-party
patents. This patent grant terminates if You initiate a patent claim alleging
that SoAI infringes Your patent rights, except where mandatory law requires a
different result.

Outside code contributions are not accepted unless and until the Licensor
publishes a contribution policy and rights process. Issue reports or suggestions
do not transfer ownership or create a right to have code merged.

## 11. Termination

Rights terminate for material breach. For a curable, non-willful breach, rights
are reinstated if You fully cure within 30 days after written notice. Deliberate
piracy, sublicensing, unlawful redistribution, fraud, or other incurable breach
may terminate immediately. Termination does not affect accrued obligations or
provisions that by their nature survive, including ownership, restrictions,
disclaimers, liability limits, and enforcement terms.

## 12. Warranty disclaimer

TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE LICENSED WORK IS PROVIDED “AS IS”
AND “AS AVAILABLE,” WITHOUT EXPRESS, IMPLIED, OR STATUTORY WARRANTIES, INCLUDING
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT,
ACCURACY, SECURITY, AVAILABILITY, OR RESULTS.

Nothing excludes a warranty, conformity obligation, remedy, or consumer right
that applicable law does not permit the parties to exclude.

## 13. Limitation of liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE LICENSOR IS NOT LIABLE FOR INDIRECT,
INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR LOST
PROFITS, REVENUE, DATA, GOODWILL, OR BUSINESS INTERRUPTION.

The Licensor's aggregate ordinary liability arising from this License will not
exceed fees paid for the affected license during the 12 months before the event,
or USD 100 if nothing was paid. These limits do not apply to fraud, intentional
wrongdoing, gross negligence, mandatory product obligations, or any liability
that applicable law does not permit the parties to limit.

## 14. Governing law and assignment

Italian law governs. This choice does not deprive a consumer of protection provided
by rules that cannot be excluded by agreement under the law that would apply
without this choice, including mandatory rules of the consumer's habitual
residence. The competent courts at the Licensor's Italian domicile have
jurisdiction only where mandatory consumer or other law does not provide a
different forum.

You may not assign a personal grant. A business customer may assign its agreement
in a merger, acquisition, corporate reorganization, or sale of substantially all
relevant assets if the successor accepts it and the customer is not in material
breach. Other assignments require written consent.

### 14.1 Notices

A notice under this License must be in writing, in English or Italian. A notice to
the Licensor is effective when delivered to the licensing contact published at
`https://soai.to/legal-notices/`, or to any other address the Licensor later
designates there or in writing. A notice to You is effective when delivered to the
contact recorded in Your entitlement, order, or acceptance record, or, where no
such record exists, to an address You have used to contact the Licensor. A notice
sent by email is treated as received on the next business day at the recipient's
location unless it is returned undelivered.

## 15. General

Mandatory law prevails. An unenforceable provision is enforced to the maximum
lawful extent and the remainder continues. A waiver must be express and written.
The Licensor may additionally release first-party material under MIT or another
license, without changing rights already granted or licensing third-party
material.

The Licensor may publish a later numbered version of this License. A later version
governs only the Official Releases distributed under it. The version that
accompanied an Official Release continues to govern Your use of that release, and
a later version cannot retroactively reduce or revoke a right You already
received. Where an entitlement recorded a document fingerprint, that exact
recorded version governs that grant.

An accepted signed order or separately negotiated agreement controls its
deal-specific terms; `COMMERCIAL-LICENSE.md` controls standard commercial use;
`ORGANIZATION-EVALUATION-TERMS.md` controls evaluations; and this License
otherwise controls the Licensed Work. `LICENSING.md` is explanatory only.
