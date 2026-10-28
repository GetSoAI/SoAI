# SoAI privacy and data handling

Version 1.1 · effective 22 August 2026

This document describes what the SoAI software does with data on the machine you
run it on, and what it sends off that machine. It is explanatory and
non-operative: it grants, limits, and varies no right. `LICENSE.md` and the other
operative documents govern licensing.

Roberto Martini develops and licenses SoAI. In this document, "the Licensor"
refers to the same person and role defined in the operative documents.

The separate privacy notice at `https://soai.to/privacy/` covers the licensing
website, checkout, and direct support records, where the Licensor is the
controller. This document covers the software itself.

## Self-hosted use

SoAI Core used under Free Personal Use requires no Licensor account, product key,
or activation. Accounts created in the SoAI WebUI belong to your installation.
SoAI includes no product analytics, usage reporting, crash reporting, heartbeat,
or periodic license check.

Local inference and installed features continue to work when `soai.to` and
`api.github.com` are blocked. Blocking these hosts prevents licensing operations,
application update checks, and downloads that use them. Prepare the runtime,
backends, and models before taking an installation offline.

You can inspect network traffic with a tool such as `tcpdump` and compare it with
the connections described below. Undisclosed connections should be reported
following `SECURITY.md`. Release checks enforce the disclosed licensing and
update destinations, reject telemetry exporter configuration, and require
ChromaDB telemetry to be disabled. The source is available for inspection,
including changes between releases.

## Application data

Your prompts, model inputs, model outputs, documents, knowledge-base content,
files, credentials, API keys, conversations, and business data stay on the
machine you run SoAI on. None of it is sent to the Licensor, for licensing or for
any other purpose. There is no analytics, no usage reporting, no crash telemetry,
and no background licensing connection.

SoAI is self-hosted. For the data you process with it, you are the controller and
the Licensor is not a processor: that data never reaches the Licensor, so there is
no application data for the Licensor to process, sell, or use for training.

## Licensing and application update connections

SoAI uses the following endpoints for licensing and application updates.

**Licensing: `https://soai.to`.** SoAI contacts this service only for an explicit
licensing operation: evaluation issuance, activation, deactivation, SoAI OS evaluation
conversion or reversion, commercial conversion, deployment reclassification, term
renewal, operation reconciliation, and offline activation. The origin is pinned in
code and no other licensing host is accepted.

Free Personal Use of SoAI Core needs no product key or activation and does not
require a connection to the licensing service.

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

Licensing requests exclude prompts, model inputs and outputs, files, provider
credentials, knowledge-base content, request counts, and usage statistics. They
also exclude the hostname, MAC address, disk or machine serial, installed-software
inventory, or hardware fingerprint: your deployment identity is a key pair
generated on your machine, not a measurement taken of it.

**Application updates: `https://api.github.com`.** SoAI uses the GitHub API to
look up official releases and obtain their download locations. Requests identify
the software with the user agent
`SoAI (+https://soai.to)` and send no account, deployment, or usage information.
Application release checks run when an update action or update-status view asks
for one; they do not run on a background schedule. Downloaded releases are verified
against a pinned Ed25519 signature before anything is installed.

As with other HTTPS requests, the receiving server observes the source IP address
and request time. The Licensor does not combine that information into a user
profile. The privacy notice at `https://soai.to/privacy/` describes the limited
server logs retained for the licensing website.

After a successful activation, entitlement validation is local. A valid
deployment keeps working through a licensing-service or website outage, and a
commercial entitlement operates offline through its written term.

## About the OpenTelemetry packages

ChromaDB (https://github.com/chroma-core/chroma), which SoAI uses for knowledge-base
storage, requires the `opentelemetry-*` and `posthog` packages as dependencies.
SoAI does not import or configure their reporting clients or set an exporter or
collector endpoint. Its ChromaDB client uses `anonymized_telemetry=False` and
`chroma_otel_granularity="none"`, disabling ChromaDB's reporting.

## What SoAI downloads, and from where

SoAI obtains required runtime components from their upstream sources when they
are not already packaged or installed. These downloads do not include your
prompts, files, account identity, or usage statistics. The receiving server can
observe the requested file, source IP address, and request time. `NOTICE` lists
the components and their licenses. Runtime preparation can obtain:

- **Playwright Chromium**, fetched by Playwright's own installer from its
  distribution service, used for browser automation.
- **Azul Zulu Builds of OpenJDK**, from `https://cdn.azul.com`, the managed Java runtime
  that runs Apache Tika.
- **The Apache Tika server distribution**, from `https://archive.apache.org`, used
  for document text extraction. Complete release packages include this archive;
  source installations download it when it is not already available.
- **The ripgrep binary**, from `https://github.com`, used for file search.
- **The tiktoken encoding files** (`vocab.bpe`, `encoder.json`, `r50k_base`,
  `p50k_base`, `cl100k_base`, and `o200k_base`), from
  `https://openaipublic.blob.core.windows.net`, cached under the state directory
  and used to count tokens locally.

`openaipublic.blob.core.windows.net` is Microsoft-operated storage for the public
encoding tables used by the `tiktoken` tokenizer. SoAI downloads and caches those
tables, then counts tokens locally. Token counting sends no prompts, text, or
user identifiers to that host or to OpenAI and needs no network connection once
the tables are cached.

On Windows, SoAI obtains its managed Python runtime from Astral's Python Build
Standalone releases on `https://github.com`. On Linux and macOS, micromamba
prepares the managed Python environment from conda-forge packages. Later Linux
and macOS starts may download required runtime security updates before the
application starts. These operations fetch software; they do not send prompts,
files, or usage statistics.

SoAI also applies the supported upstream opt-outs for inference-engine usage
reporting, Hugging Face telemetry and update checks, pip version checks, and
ONNX Runtime telemetry. Local OCR explicitly disables ONNX Runtime telemetry.
Third-party plugins remain responsible for their own network behavior.

Two further downloads happen only when you use the feature that needs them:

- **The EasyList filter list**, from `https://easylist.to`, fetched the first
  time browser automation runs with ad blocking enabled
  (`TOOLS.MCP.BROWSER.BLOCK_ADS`, on by default). Turn it off, or point
  `TOOLS.MCP.BROWSER.AD_BLOCK_LIST_URL` at your own copy.
- **A public test file**, from `https://ftp.gnu.org`, downloaded and discarded
  only when you start the network speed measurement in hardware benchmarking.

Installing or updating an inference backend obtains its packages from upstream
sources such as `https://download.pytorch.org`. Model downloads use the selected
registry, such as `https://huggingface.co`. Built-in backend updates can download
automatically when `PLUGINS.BACKEND_UPDATES.AUTO_UPDATE_BUILTIN` is enabled;
third-party backend updates remain manual.

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

SoAI provides no Licensor remote administration channel or support tunnel. The
Licensor cannot access or read your installation remotely through the product.

License expiry never changes this. When an evaluation or commercial term ends,
application functionality is restricted, but licensing, status, logs, data access,
backup and export, recovery, and limited safe repair remain available, and the
operating system and your data are never locked.

## If you deploy SoAI for other people

When an organization runs SoAI for its users, that organization is the controller
for the data its users put into it, and is responsible for lawful basis,
transparency, retention, security, and data-subject requests. The Licensor is not
a processor for that data, because it never receives it.

You may choose to send diagnostic material to the Licensor when requesting
support. `COMMERCIAL_SUPPORT_TERMS.md` requires that diagnostic material be
minimized and that secrets be excluded, and the privacy notice at `https://soai.to/privacy/`
describes how support records are handled. Nothing is collected from your
installation for support unless you send it yourself.

## Reporting

If you believe SoAI sends something this document does not describe, report it as
a security issue following `SECURITY.md`. Include undisclosed destination hosts
as well as unexpected data transfers in the report.

Questions about this document, and data-protection requests concerning the
licensing, checkout, and support records the Licensor does hold, go to
`privacy@soai.to`. The privacy notice at `https://soai.to/privacy/` governs those
records.
