# Commercial licensing availability

Status: temporary operational restriction, introduced before the first public SoAI release.

This file records the cosmetic commercial-use soft lock so it can be removed cleanly. It does not amend the SoAI
licenses, change any grant, revoke an issued entitlement, or alter the backend licensing implementation.

## Current availability

- SoAI Core is available for free Personal Use under the controlling license.
- Commercial licenses and organization evaluations are temporarily unavailable and are not currently being issued.
- SoAI OS is temporarily unavailable and is not currently distributed.
- Companies and organizations can contact `info@soai.to` for licensing information or to join the waitlist for future
  availability.
- Joining the waitlist grants no license and does not guarantee an availability date.

## Soft lock implementation

The backend licensing API, entitlement validation, evaluation flow, checkout implementation, and controlling license
documents remain unchanged. A caller that deliberately uses the backend API can still reach the existing licensing
behavior. This is intentional: the restriction is a reversible WebUI and website soft lock, not a licensing refactor.

The normal WebUI paths are disabled as follows:

- `frontend/assets/ts/pages/wizard/view.ts` keeps the organization/commercial choice visible but disables its radio
  input. The card remains keyboard-focusable and displays the localized standard tooltip.
- `frontend/assets/css/pages/wizard/licensing.css` gives that disabled card a disabled cursor and appearance without
  changing the shared tooltip system.
- `frontend/assets/ts/pages/settings/controllers/licensing/view.ts` disables the later change from Personal Use to
  organization/commercial use and displays the same availability message.
- `frontend/assets/lang/*.json` defines `licensing.base.unavailableTooltip` in every supported language. The English
  message directs users to `info@soai.to` for information or the waitlist.

The public website stops presenting commercial or SoAI OS sales as currently available:

- `soai.to/index.html` presents Personal Use as free, commercial licensing as waitlist-only, and SoAI OS as unavailable.
- `soai.to/legal-source/licensing.html` adds the current availability notice and removes the live checkout call to
  action while retaining planned terms for transparency.
- `soai.to/assets/data/software-application.jsonld` advertises only the free Personal Use offer.
- `release_tools/editions/source_stage.py`, `release_tools/editions/profile_stage.py`, and
  `release_tools/editions/public_source_policy.py` include this document in source, public-source, Core, OS, and
  platform release artifacts. `.gitignore` allows the root file into Git history, the V1 public-source manifest contains
  its exact mapping, and the edition staging contract verifies it survives staging.

No waitlist database or automated enrollment was added. The waitlist is handled by email.

## Reversal checklist

When commercial licensing can be accepted again:

1. In the wizard view, remove the disabled card state, focus and tooltip attributes, disabled radio attribute, and the
   `commercialUnavailableTooltip` value.
2. In the wizard licensing stylesheet, restore hover/selection styling for every choice card and remove the
   `.is-disabled` rule.
3. In the Settings licensing view, restore the organization action help to an empty value and make the action depend on
   `operationInProgress` again.
4. Remove `licensing.base.unavailableTooltip` from all 22 translation catalogs and regenerate the frontend translation
   key types.
5. Restore the commercial and SoAI OS availability copy, commercial structured-data offer, and checkout link on the
   real website. The generic work-in-progress splash has no licensing-specific state to reverse.
6. If this operational record should no longer ship, remove its `.gitignore` opt-in, its entries in the three release
   staging policies, and its edition staging assertions, then regenerate the V1 public-source manifest.
7. Run the focused licensing tests, the frontend build, `./frontend_check/frontend_check.sh`, and the website verifier.

No backend endpoint, database schema, entitlement code, checkout code, legal-document hash, or license document needs
to be restored or migrated when this soft lock is removed.
