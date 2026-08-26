/* SoAI - Settings feature external account modal session model [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalSessionModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CALENDAR_DESCRIPTOR, MAIL_DESCRIPTOR, type ExternalAccountDescriptor } from '@features/settings/externalaccounts/descriptors.ts';
import type { ExternalAccountModalMode } from '@features/settings/externalaccounts/externalAccountModalTypes.ts';
import type { CalendarAccountEntry, CalendarAccountWriteRequest, ExternalAccountEntry, ExternalAccountType, MailAccountEntry, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';

interface ExternalAccountModalSessionState {
    mode: ExternalAccountModalMode;
    accountType: ExternalAccountType | null;
    currentAccount: ExternalAccountEntry | null;
    baselineSnapshot: string;
}

type ExternalAccountSessionDescriptor = ExternalAccountDescriptor<'mail', MailAccountEntry, MailAccountWriteRequest> | ExternalAccountDescriptor<'calendar', CalendarAccountEntry, CalendarAccountWriteRequest>;

const resolveExternalAccountDescriptor = (accountType: ExternalAccountType): ExternalAccountSessionDescriptor => {
    return accountType === 'mail' ? MAIL_DESCRIPTOR : CALENDAR_DESCRIPTOR;
};

export { resolveExternalAccountDescriptor };
export type { ExternalAccountModalSessionState, ExternalAccountSessionDescriptor };
