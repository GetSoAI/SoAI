# SoAI Security Policy

## Single point of contact

`security@soai.to` is the single point of contact for reporting vulnerabilities in SoAI and for receiving security information about it. The same contact is published at `https://soai.to/legal-notices/`. Roberto Martini is the manufacturer of SoAI for the purposes of Regulation (EU) 2024/2847.

## Reporting a vulnerability

Report suspected vulnerabilities privately to `security@soai.to` with the subject `SoAI security report`.

Include the affected version or revision, deployment platform, prerequisite access, reproduction steps, impact, and any proof-of-concept material that can be shared safely. Do not include live credentials, private user data, or destructive payloads. If sensitive attachments are necessary, request a secure transfer method first.

Do not publish an undisclosed vulnerability or open a public issue containing exploit details. Good-faith testing must be limited to systems and data you own or are explicitly authorized to test. Do not perform denial-of-service testing, persistence, social engineering, data exfiltration, or testing against other users.

## Handling

Reports are validated and prioritized by exploitability and impact, and receipt is acknowledged on the timeline in the next section. If a report is accepted, remediation and disclosure timing is coordinated with the reporter. There is no bug bounty, and no particular remediation outcome is promised for a report that turns out not to describe a vulnerability in SoAI.

The supported security baseline is the latest available stable SoAI release. Superseded releases are not maintained for feature parity or guaranteed separate security fixes. A report affecting an older release may be asked to reproduce the issue against the latest stable release before investigation continues.

## Coordinated disclosure

Reports are handled under coordinated disclosure on these timelines, counted in business days at Europe/Rome:

| Stage | Target |
| --- | --- |
| Acknowledge receipt | 5 days |
| Initial assessment and severity decision | 10 days |
| Fix or documented mitigation for a confirmed high or critical issue | 90 days |
| Public advisory | when the fix ships, or 90 days after acknowledgement, whichever comes first |

A reporter who wants to publish earlier is asked to say so; disclosure timing is agreed rather than imposed, and no embargo is required as a condition of the report being handled. An issue found to be actively exploited is treated as critical and remediated ahead of these targets. Reporters are credited in the advisory on request. These are targets for a coordinated process, not a service-level commitment and not part of any paid support entitlement.

Advisories are published on the GitHub repository's security advisories page and referenced from the release notes.

## Support period and security updates

The security support period for SoAI runs from **22 August 2026 to 22 August 2031**, five years after the first official public distribution recorded in `CHANGE-DATES.md`. During that period, security updates are provided for the latest available stable release. This does not promise continued maintenance, feature parity, or separate security backports for superseded releases. That period reflects the expected lifetime of the product and is stated for Article 13(8) of Regulation (EU) 2024/2847.

During the support period, security updates for the latest stable release are published **free of charge to everyone**, whether or not a paid commercial term is active and whether the installation is personal, evaluation, or commercial. They are delivered as official signed numbered releases through the same verified updater path as any other release, and are announced in the advisory and the release notes. Receiving a security update does not by itself grant a right to use SoAI outside a valid grant, and it does not extend or renew a license term.

Security updates are shipped separately from feature work wherever a targeted fix is practical, so that applying one does not require adopting unrelated change.

## Software bill of materials

`licenses/SBOM-PYTHON-CYCLONEDX.json` is the machine-readable SBOM for the Python dependencies pinned in `requirements.txt`, in CycloneDX 1.6 JSON, with a package URL and license record for every component. The release process regenerates it and proves that the published document matches the current requirements.

Those dependencies are installed into SoAI's managed runtime environment at first start rather than shipped inside the release archive. Components of the built frontend bundle are recorded in `licenses/FRONTEND-THIRD-PARTY-LICENSES.txt`, Android components in the notice published by the separate SoAI Connect repository, and runtime-downloaded artifacts such as Chromium, the Java runtime, Apache Tika, and ripgrep in `NOTICE`.

## Regulatory reporting

From 11 September 2026, Article 14 of Regulation (EU) 2024/2847 requires the manufacturer to notify ENISA and the relevant CSIRT of an actively exploited vulnerability in SoAI, or a severe incident affecting its security, with an early warning within 24 hours of becoming aware of it. Reports sent to `security@soai.to` are assessed against that obligation as part of the initial triage above. Reporting to the authorities does not replace the advisory published to users, and a reporter's identity is not disclosed in it.

## Release authenticity

Official complete releases include a V1 JSON manifest signed with Ed25519. The automatic updater verifies that signature against the public key pinned in SoAI and validates the selected archive and every contained regular file before installation. A checksum alone is not an authenticity guarantee; use the signed manifest and obtain artifacts from the official release location.

The SHA-256 fingerprint of the raw 32-byte Ed25519 production public key is:

```text
e0333589b1ca792397182cc3f843989c021a056c61e281f8456c1da4f479f2a7
```

For an initial download, compare this fingerprint with the copy published in the trusted SoAI source repository before trusting the key or artifacts obtained from a release page. From a trusted complete installation or source tree with its managed runtime installed, invoke the public verifier as `PYTHONPATH=backend soai_main_venv/bin/python -m app.updater.offline_release_verification` and supply the release directory, version, Core version, edition, public-key path, and expected fingerprint. The verifier validates the exact release set, signature, sidecars, artifact hashes, required platform payloads, frontend bundles, and signed archive inventories.
