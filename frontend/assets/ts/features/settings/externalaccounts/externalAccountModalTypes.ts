/* SoAI - Settings feature external account modal types [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CalendarAccountEntry, ExternalAccountEntry, ExternalAccountType, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';

type ExternalAccountModalMode = 'launcher' | 'create' | 'edit';

interface ExternalAccountModalOpenOptions {
    host: ExternalAccountsManagerHost;
    mode: ExternalAccountModalMode;
    accountType?: ExternalAccountType | null | undefined;
    account?: ExternalAccountEntry | null | undefined;
    getMailAccounts: () => MailAccountEntry[];
    findMailAccount: (accountId: string) => MailAccountEntry | null;
    findCalendarAccount: (accountId: string) => CalendarAccountEntry | null;
    reload: () => Promise<boolean>;
}

export type { ExternalAccountModalMode, ExternalAccountModalOpenOptions };
