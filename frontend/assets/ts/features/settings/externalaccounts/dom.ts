/* SoAI - Settings feature external accounts DOM contracts [frontend/assets/ts/features/settings/externalaccounts/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';

const EXTERNAL_ACCOUNTS_ROOT_ID = 'external-accounts-content';
const EXTERNAL_ACCOUNTS_ADD_BUTTON_ID = 'external-accounts-add-button';
const MAIL_LIST_ID = 'external-accounts-mail-list';
const CALENDAR_LIST_ID = 'external-accounts-calendar-list';
const MAIL_COUNT_ID = 'external-accounts-mail-count';
const CALENDAR_COUNT_ID = 'external-accounts-calendar-count';
const MAIL_AVAILABILITY_ID = 'external-accounts-mail-availability';
const CALENDAR_AVAILABILITY_ID = 'external-accounts-calendar-availability';

const requireRoot = (host: ExternalAccountsManagerHost): HTMLElement => host.pageDom.requireHTMLElement(`#${EXTERNAL_ACCOUNTS_ROOT_ID}`);

export { CALENDAR_AVAILABILITY_ID, CALENDAR_COUNT_ID, CALENDAR_LIST_ID, EXTERNAL_ACCOUNTS_ADD_BUTTON_ID, EXTERNAL_ACCOUNTS_ROOT_ID, MAIL_AVAILABILITY_ID, MAIL_COUNT_ID, MAIL_LIST_ID, requireRoot };
