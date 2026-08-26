# SoAI privacy and data handling

Version 1.1 · effective 22 August 2026

This document describes what the SoAI software does with data on the machine you
run it on, and what it sends off that machine. It is explanatory and
non-operative: it grants, limits, and varies no right. `LICENSE.md` and the other
operative documents govern licensing.

I am Roberto Martini, the individual who writes and licenses SoAI. Where this
document says "I", it means me. Where it says "the Licensor", it means the same
person acting in the role the operative documents define.

The separate privacy notice at `https://soai.to/privacy/` covers the licensing
website, checkout, and direct support records, where the Licensor is the
controller. This document covers the software itself.

## If you self-host, start here

You have probably been burned before. Most software you install now assumes it
may watch you: "anonymous usage statistics" enabled by default, an account
required to run something on your own hardware, a license check that phones home
on a timer, a crash reporter that ships your file paths to a vendor, an
"improvement programme" you never joined. SoAI does none of that, and this
section exists so that you never have to take my word for it.

- **No account, ever, for free personal use.** SoAI Core used personally needs no
  product key, no sign-up, and no activation. There is nothing of mine to log in
  to.
- **There is no telemetry to opt out of.** No analytics, no usage reporting, no
  crash telemetry, no heartbeat, no periodic license check, and no update ping on
  a timer. Nothing is merely "off by default" — nothing is there.
- **Block me at the firewall and keep working.** Deny `soai.to` and
  `api.github.com`. SoAI runs. You lose explicit licensing operations and the
  ability to look for updates. You lose nothing else. An installation used for
  free personal use has no reason to reach either host at all.
- **Watch the wire.** Point `tcpdump` at a fresh install and compare what you see
  against "What SoAI downloads, and from where" below. That list is meant to be
  exhaustive. If it is not, that is a defect in my software or in this document,
  and I want the report.
- **The claims are enforced in the release process, not just asserted here.**
  Release verification fails if licensing or update code reaches a host this document does not
  disclose, if a telemetry exporter appears anywhere in the backend, or if the
  ChromaDB client is constructed without its telemetry disabled.
- **The source is available.** Adding tracking to SoAI would take a commit, and
  that commit would be visible. You do not have to trust a promise about the
  future; you can read the diff.

I do not want your data. There is no server of mine for it to arrive at, which
means there is nothing for me to mine, profile, sell, share with an advertiser,
or be compelled to produce about you.

## The short version

Your prompts, model inputs, model outputs, documents, knowledge-base content,
files, credentials, API keys, conversations, and business data stay on the
machine you run SoAI on. None of it is sent to the Licensor, for licensing or for
any other purpose. There is no analytics, no usage reporting, no crash telemetry,
and no background phone-home.

SoAI is self-hosted. For the data you process with it, you are the controller and
the Licensor is not a processor: that data never reaches the Licensor, so there is
nothing for the Licensor to process, sell, mine, or train on.

## What SoAI contacts on its own

Only two first-party endpoints, and only for the reasons below.

**`https://soai.to` — licensing.** Contacted only for an explicit licensing
operation: evaluation issuance, activation, deactivation, SoAI OS evaluation
conversion or reversion, commercial conversion, deployment reclassification, term
renewal, operation reconciliation, and offline activation. The origin is pinned in
code and no other licensing host is accepted.

Free personal use of SoAI Core needs no product key and no activation, so an
installation used that way has no reason to contact the licensing service at all.

Each licensing request is signed with a deployment key generated on your machine
and carries only:

- the deployment's public key, deployment identifier, and instance identifier
- the SoAI version, product edition, and entitlement generation
- an idempotency key and a request nonce
- which legal documents were accepted, with their version and SHA-256 fingerprint
- for an activation, the product key you entered, and whether you declared the
  deployment production or non-production
- for a deactivation, which of four fixed reasons applies: `rehost`, `retired`,
  `disaster_recovery`, or `other`. Free text is not accepted
- for organization evaluation and commercial flows only, the identity you supply
  for the contract: legal name, country, registration or tax identifier, the
  authorized acceptor's name and email, and the attestations those flows require

It carries no prompt, no model input or output, no file, no credential, no
knowledge-base content, no request counts, and no usage statistics. It also
carries no hostname, MAC address, disk or machine serial, installed-software
inventory, or hardware fingerprint: your deployment identity is a key pair
generated on your machine, not a measurement taken of it.

**`https://api.github.com` — updates.** Used to look up official releases and
download release assets. Requests identify the software with the user agent
`SoAI (+https://soai.to)` and send no account, deployment, or usage information.
There is no scheduled background update polling: a check happens when an update
action or update-status view asks for one. Downloaded releases are verified
against a pinned Ed25519 signature before anything is installed.

Both are ordinary HTTPS requests, so the receiving server necessarily observes
the source IP address and the time of the request, exactly as it would for any
web request you make. I do not join that to a profile, and the bounded, minimized
server logging that results is described in the notice at
`https://soai.to/privacy/`. Blocking both hosts removes even that.

After a successful activation, entitlement validation is local. A valid
deployment keeps working through a licensing-service or website outage, and a
commercial entitlement operates offline through its written term.

## About the OpenTelemetry packages

The `opentelemetry-*` packages and `posthog` appear in `requirements.txt` only
because ChromaDB (https://github.com/chroma-core/chroma), used for knowledge-base
storage, forces them as transitive dependencies; they were never wanted or added
deliberately, nothing in SoAI imports or configures them, no exporter or collector
endpoint is ever set, and SoAI constructs its only Chroma client with
`anonymized_telemetry=False` and `chroma_otel_granularity="none"`, so ChromaDB's
own reporting is off and no telemetry leaves your machine.

## What SoAI downloads, and from where

Runtime components are fetched from their own upstream sources on first use, not
from me. These are downloads to your machine, not uploads of your data: each is a
plain file fetch carrying no identifier of yours, and none of these hosts learns
anything about how you use SoAI. They are listed with their licenses in `NOTICE`.
The complete set fetched during first start is:

- **Playwright Chromium**, fetched by Playwright's own installer from its
  distribution service, used for browser automation.
- **Microsoft Build of OpenJDK**, from `https://aka.ms`, the managed Java runtime
  that runs Apache Tika.
- **The Apache Tika server JAR**, from `https://archive.apache.org`, used for
  document text extraction.
- **The ripgrep binary**, from `https://github.com`, used for file search.
- **The tiktoken encoding files** (`vocab.bpe`, `encoder.json`, `r50k_base`,
  `p50k_base`, `cl100k_base`, and `o200k_base`), from
  `https://openaipublic.blob.core.windows.net`, cached under the state directory
  and used to count tokens locally.

That last host deserves a plain explanation, because it is the one that looks
alarming in a packet capture. It is Microsoft-operated storage from which OpenAI
publishes the public encoding tables that the `tiktoken` tokenizer needs. SoAI
downloads those tables once and counts tokens entirely on your machine. No
prompt, no text, and no identifier is sent to that host or to OpenAI, and nothing
about token counting requires a network connection after the files are cached.

Two further downloads happen only when you use the feature that needs them:

- **The EasyList filter list**, from `https://easylist.to`, fetched the first
  time browser automation runs with ad blocking enabled
  (`TOOLS.MCP.BROWSER.BLOCK_ADS`, on by default). Turn it off, or point
  `TOOLS.MCP.BROWSER.AD_BLOCK_LIST_URL` at your own copy.
- **A public test file**, from `https://ftp.gnu.org`, downloaded and discarded
  only when you start the network speed measurement in hardware benchmarking.

Installing an inference backend also downloads that backend's own packages and
models from its own upstream, such as `https://download.pytorch.org` or a model
registry like `https://huggingface.co`, and only when you choose to install it.

## What you point SoAI at

SoAI is an orchestration layer, so most network traffic goes where you configure
it to go. Inference backends, OpenAI-compatible providers, model registries,
search providers, image services, mail and calendar accounts, messaging
integrations, and browser automation targets are contacted only when you set them
up and use them.

Data you send to those services is governed by their terms and privacy policies,
not by this document. Local inference backends keep that data on your own
hardware. Choosing a remote provider means your prompts and content go to that
provider; the Licensor is not party to it and never receives a copy.

## What stays on your machine

Configuration, credentials and vault secrets, the SoAI database, conversation and
message history, knowledge-base documents and embeddings, uploaded and generated
files, logs, and hardware statistics are stored locally under the installation's
data directory. You control retention, backup, encryption at rest, and deletion.

SoAI ships no remote administration channel, no vendor backdoor, and no support
tunnel that I can open. The Licensor has no access path to your installation and
no ability to read it remotely.

License expiry never changes this. When an evaluation or commercial term ends,
application functionality is restricted, but licensing, status, logs, data access,
backup and export, recovery, and limited safe repair remain available, and the
operating system and your data are never locked.

## If you deploy SoAI for other people

When an organization runs SoAI for its users, that organization is the controller
for the data its users put into it, and is responsible for lawful basis,
transparency, retention, security, and data-subject requests. The Licensor is not
a processor for that data, because it never receives it.

Support is the one place where you may choose to send material to the Licensor.
`COMMERCIAL-SUPPORT-TERMS.md` requires that diagnostic material be minimized and
that secrets be excluded, and the privacy notice at `https://soai.to/privacy/`
describes how support records are handled. Nothing is collected from your
installation for support unless you send it yourself.

## Reporting

If you believe SoAI sends something this document does not describe, report it as
a security issue following `SECURITY.md`. Treat it as a defect, not a
documentation gap. That applies to a host missing from the download list above
just as much as to anything else.

Questions about this document, and data-protection requests concerning the
licensing, checkout, and support records the Licensor does hold, go to
`privacy@soai.to`. The privacy notice at `https://soai.to/privacy/` governs those
records.
