# SoAI Standard Commercial License 1.0

Document ID: `standard_commercial_license`

Version 1.0 — effective 22 August 2026

These terms are between Roberto Martini (the **Licensor**) and the natural person
acting as a sole proprietor, or the legal or collective entity, identified in an
accepted order (the **Customer**). They govern the standard annual commercial
offers. A separately signed private agreement controls its expressly negotiated
rights.

## 1. Activation and accepted documents

Commercial rights begin only after the Customer accepts the exact order and
governing document versions, Paddle confirms and the licensing service reconciles
the completed payment, and a matching signed entitlement is issued. Possession of
source, a credential, or a provider record alone creates no right.

The Customer must provide accurate legal identity, country, registration or tax
identifier, and an authorized natural-person acceptor. The acceptor attests that
they may bind the Customer. Immutable acceptance records bind the order, offer,
price, term, automatic-renewal disclosure, and exact SHA-256 document
fingerprints.

## 2. Standard offers

The initial offers are:

| Offer | Price and cadence | Licensed product scope | Included support |
| --- | --- | --- | --- |
| Core Commercial | USD 499 per year, automatic renewal | standalone SoAI Core | 1 professional hour per term |
| SoAI OS Commercial | USD 799 per year, automatic renewal | SoAI OS and Core components inside each OS deployment | 2 professional hours per term |
| Core + OS Commercial | USD 999 per year, automatic renewal | standalone Core and SoAI OS | 4 professional hours per term |

Prices exclude taxes and legally required checkout charges presented by Paddle.
A purchased term and price do not change retroactively. Discounts or different
future prices do not alter an accepted order.

## 3. Deployment allowance

Each standard offer permits three active production and three active
non-production control-plane deployments during the paid term. Non-production
means development, staging, testing, or disaster-recovery rehearsal. Backups and
powered-off cold disaster-recovery copies that serve no traffic and cannot operate
concurrently do not consume a slot.

A deployment is one independently managed SoAI control plane with one licensing
identity, regardless of users, GPUs, models, inference engines, workers, requests,
or downstream workloads. Replicas count as one only if they are a single logical
high-availability control plane, share configuration and one entitlement, and
cannot operate independently. A separately operable control plane or traffic-
serving standby is another deployment. A cold replacement may take over a slot
after the prior deployment stops.

Core Commercial permits standalone Core deployments only. SoAI OS Commercial
permits OS deployments and their integrated Core components, but no separate
Core-only deployment. Core + OS shares one three-production and one three-non-
production pool across Core and OS; it does not provide separate pools per form.

### 3.1 Self-certification

At most once per twelve-month term, on at least 30 days' written notice, the
Licensor may ask the Customer to confirm in writing the number of active
production and non-production deployments then in use and the entitlement each one
runs under. A written confirmation by an authorized representative satisfies the
request in full.

This is not an audit right. The Licensor may not require on-site inspection,
access to Customer systems, networks, or data, installation of measurement
software, or review by a third-party auditor. If a confirmation shows more
deployments than the allowance, the Customer may cure by reducing deployments or
purchasing the additional capacity within 30 days, without penalty, interest, or
back-dated fees. This obligation survives termination for one year.

## 4. Customer and controlled affiliates

The Customer includes entities it directly or indirectly controls only while each
participating affiliate is identified when reasonably requested, accepts the
applicable terms, and uses the Customer's shared allowance. An affiliate receives
no separate capacity, resale, or sublicense right and loses participation when it
ceases to be controlled. The Customer remains responsible for affiliates and
contractors.

## 5. Permitted commercial use

Within the paid term, product scope, and deployment allowance, the Customer may:

1. use SoAI internally for lawful business purposes;
2. expose SoAI's OpenAI-compatible and Anthropic-compatible APIs and MCP capabilities;
3. provide hosted inference, orchestration, SoAI WebUI access retaining SoAI's
   identity, SaaS, managed services, agents, automations, chatbots, search,
   customer-facing applications, and inference platforms;
4. serve any number of users and workloads without per-seat, per-GPU, per-model,
   or per-request fees;
5. make and use private modifications and necessary internal source copies,
   containers, VM images, installation media, and backups; and
6. give contractors confidential copies strictly necessary to operate the
   Customer's licensed deployment, subject to use solely for the Customer and
   return or deletion afterward.

An agency may host licensed deployments for clients while retaining operational
control. A client needs its own license if it receives an independently operated
installation or control plane. End users may consume a service but receive no
right to copy, install, distribute, or sublicense SoAI. A separately created
website, client, chatbot, or SaaS interface needs no SoAI badge merely because it
uses SoAI, but SoAI-supplied interfaces and distributed internal copies must retain
required identity and notices.

## 6. Restrictions and reserved private deals

Standard terms do not permit distribution of substantially complete SoAI source
or binaries, downloadable or on-premises embedding in a third-party product,
independent client transfer, sublicensing, OEM delivery, resale of software copies,
white-labeling, removal of notices or SoAI identity, or representing a modified
version as official.

Perpetual commercial, OEM, product-building, redistribution, sublicensing,
white-label, additional capacity, and broader trademark rights require a separate
signed private agreement. Unless that agreement says otherwise, it is non-
exclusive, ownership stays with the Licensor, later versions are not included,
and the Licensor remains free to develop and license SoAI.

## 7. Term, renewal, continuity, and expiry

Term dates come from mutually consistent reconciled Paddle transaction and
subscription billing facts stated in the signed entitlement; they are never
created by adding a local year. The entitlement operates without recurring
licensing contact through its written term.

Automatic renewal and cancellation follow the accepted checkout and Paddle buyer
terms. Cancellation stops future renewal but does not itself create a refund. A
failed renewal creates no next term and does not shorten the current one.

Only when timely renewal payment completed but a licensing-service failure prevents
normal term delivery may the Licensor issue one signed, non-stackable continuity
record for no more than 30 days after the previous term. It preserves the same
deployment, product, environment, and capacity scope; is not a free renewal; does
not cover late, missing, failed, refunded, mismatched, or reused payment evidence;
and is superseded by the paid term when delivery becomes possible.

At expiry, SoAI application functionality becomes restricted, but licensing,
status, logs, data access, backup/export, recovery, and limited safe repair remain
available. Expiry never locks Debian or Customer data.

## 8. Updates and support

The Customer may use generally released updates for the purchased product scope
while the paid term is active. Updates are not promised on a particular schedule.
The updater accepts only official signed numbered releases and retains the last
valid installation on failure.

Security updates are different. During the support period declared in
`SECURITY.md`, security updates for supported releases are published free of
charge to everyone, whether or not a paid term is active. Receiving one does not
by itself grant a right to use SoAI outside a valid grant, and does not extend or
renew a term.

`COMMERCIAL-SUPPORT-TERMS.md` governs the included support entitlement. Licensing
and billing assistance does not consume professional-support time. Support grants
no additional software right.

## 9. Refunds, adjustments, and adverse status

Paddle is the authorized reseller and merchant of record for Paddle transactions.
Paddle's accepted buyer terms govern payment, taxes, invoices, cancellation, and
refund processing within their scope. Mandatory consumer rights remain unaffected.

A provider event alone does not silently terminate software rights. A verified full
refund, chargeback, fraud finding, legal requirement, or material-breach decision
may cause an explicit signed suspension or termination consistent with the accepted
terms and law. Partial adjustments are evaluated according to their actual scope.
Safe access to Customer data remains available.

## 10. Customer data and responsibility

The Customer owns its inputs, data, configurations, independent code, and outputs
to the extent provided by law and third-party terms. The Licensor acquires no
ownership merely because material passes through SoAI. The Customer is responsible
for security, backups, providers, models, plugins, outputs, lawful use, and every
third-party charge or term. No AI output is promised accurate, lawful, safe, or
suitable for consequential decisions.

### 10.1 Data protection

SoAI is self-hosted. Prompts, model inputs and outputs, documents, knowledge-base
content, files, credentials, and business data processed in the Customer's
deployments stay on infrastructure the Customer controls and are never
transmitted to the Licensor. The Customer is the controller for personal data in
that material. The Licensor is not a processor of it, because it never receives
it and has no access path to it. `PRIVACY.md` describes exactly what the software
sends and what it never sends.

The Licensor is an independent controller for the limited personal data it
receives to form and administer this agreement: the legal identity, country,
registration or tax identifier, and authorized acceptor's name and email recorded
in an order, acceptance record, or entitlement, together with licensing request
metadata. Paddle is an independent controller for the payment data it collects as
merchant of record. The privacy notice published at `https://soai.to/privacy/`
states purposes, legal bases, retention, and data-subject rights.

Support is the one place where the Customer may choose to send personal data to
the Licensor. Where diagnostic material submitted under
`COMMERCIAL-SUPPORT-TERMS.md` contains personal data, the Licensor processes it
as the Customer's processor, and this article is the written contract required by
Article 28(3) of Regulation (EU) 2016/679. The subject matter is the provision of
that support; the duration is the paid term plus the retention period stated in
the privacy notice; the nature and purpose are diagnosing and resolving the
reported fault; the personal data is whatever the Customer includes in a report
after the minimization required by section 4 of the support terms; and the data
subjects are the Customer's personnel and users. For that material the Licensor
will:

1. process it only on the Customer's documented instructions, including as to
   transfers, unless European Union or Italian law requires otherwise, in which
   case the Licensor will inform the Customer before processing unless that law
   forbids it;
2. bind every person authorized to process it to confidentiality;
3. apply the technical and organizational measures required by Article 32;
4. engage a sub-processor only under the general written authorization given
   here, keep the current sub-processor list in the privacy notice, give at least
   30 days' notice before adding or replacing one so the Customer may object,
   impose equivalent obligations by contract, and remain fully liable for it;
5. notify the Customer without undue delay after becoming aware of a personal
   data breach affecting it;
6. assist the Customer, so far as possible and proportionate to the nature of the
   processing, with data-subject requests and with Articles 32 to 36;
7. delete or return it at the Customer's choice when the support case closes or
   the agreement ends, except where law requires retention; and
8. make available the information reasonably necessary to demonstrate compliance
   with this article and contribute to audits by the Customer or a mandated
   auditor, conducted through documented information exchange unless mandatory
   law requires otherwise.

The Licensor processes this material in Italy. Any transfer outside the European
Economic Area will rely on an adequacy decision or on the European Commission's
standard contractual clauses. A Customer whose procurement requires a separate
data-processing agreement may request one; where a separately signed
data-processing agreement conflicts with this article, that agreement controls
for the processing it covers.

## 11. Ownership, notices, and patents

SoAI is licensed, not sold. The Licensor retains all rights not expressly granted.
Required copyright, license, attribution, third-party, and SoAI identity notices
must remain in SoAI source, internal copies, and SoAI-supplied interfaces. Truthful
nominative references are permitted without implying endorsement.

For the paid scope and term, the Licensor grants the limited patent license stated
in the applicable product license. It does not assert that a patent exists or
warrant non-infringement.

## 12. Confidentiality

Each party will protect the other's non-public business, security, personal, and
technical information using reasonable care and use it only to perform the
agreement. Exclusions apply to information public without breach, already lawfully
known, independently developed, or lawfully received without restriction. Legally
compelled disclosure is permitted with notice where lawful. Trade secrets remain
protected while they qualify; other confidentiality duties survive three years.

## 13. Warranty and liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, SOAI AND SUPPORT ARE PROVIDED “AS IS” AND
“AS AVAILABLE,” WITHOUT WARRANTIES OF MERCHANTABILITY, FITNESS, TITLE,
NON-INFRINGEMENT, ACCURACY, SECURITY, AVAILABILITY, OR RESULTS, EXCEPT EXPRESS
PAID OBLIGATIONS AND NON-WAIVABLE RIGHTS.

Neither party is liable for indirect, incidental, special, consequential,
exemplary, or punitive damages, or lost profits, revenue, data, goodwill, or
business interruption, where lawful. Aggregate ordinary liability is limited to
fees paid for the affected license during the 12 months before the event. Limits
do not apply to fraud, intentional wrongdoing, gross negligence, confidentiality
breach, mandatory product obligations, or liability that law does not permit the
parties to limit.

## 14. Breach, assignment, and law

Material breach may terminate rights after written notice and a reasonable 30-day
cure opportunity where curable. Deliberate piracy, sublicensing, unlawful
redistribution, fraud, or incurable breach may result in immediate suspension or
termination. Accrued payment, confidentiality, ownership, restrictions,
disclaimers, liability, and enforcement provisions survive.

The Customer may assign the agreement in a merger, acquisition, corporate
reorganization, or sale of substantially all relevant assets if the successor
accepts it and the Customer is not in material breach. Other assignment requires
written consent.

Each party must comply with the export control and economic sanctions law that
applies to it, including European Union and Italian restrictive measures. The
Customer must not use, receive, export, re-export, or make SoAI available in or to
a territory, government, entity, or person covered by such a measure, and confirms
that it is not such a person and is not acting on behalf of one. The Licensor may
refuse, suspend, or terminate an entitlement where continuing would breach such a
measure. This obligation survives termination.

A notice under these terms must be in writing, in English or Italian. A notice to
the Licensor is effective when delivered to the licensing contact published at
`https://soai.to/legal-notices/`, or to any other address the Licensor later
designates there or in writing. A notice to the Customer is effective when
delivered to the contact recorded in its order, entitlement, or acceptance record.
A notice sent by email is treated as received on the next business day at the
recipient's location unless it is returned undelivered.

Italian law governs and the competent courts at the Licensor's Italian domicile
have jurisdiction, except where mandatory law requires otherwise. Mandatory law
prevails. An accepted order controls deal-specific terms; these terms control
standard commercial use; each product license controls its files; support terms
control support only.
