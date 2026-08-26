/* SoAI - Settings feature external accounts contracts [frontend/assets/ts/features/settings/externalaccounts/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CalendarAccountEntry, CalendarAccountWriteRequest, MailAccountEntry, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsEndpoints } from '@core/api/endpoints/webuiExternalAccounts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';

type FormMode = 'create' | 'edit';

interface ExternalAccountsManagerHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    api: {
        webui: {
            mail: { accounts: ExternalAccountsEndpoints<MailAccountEntry, MailAccountWriteRequest> };
            calendar: { accounts: ExternalAccountsEndpoints<CalendarAccountEntry, CalendarAccountWriteRequest> };
        };
    };
    runWithBoundary: <Result>(name: string, task: () => Promise<Result> | Result) => Promise<Result>;
    withButtonDisabled: <Result>(button: Element | null, operation: () => Promise<Result>, options?: { keepDisabled?: boolean }) => Promise<Result>;
    confirmAndExecute: <Result>(boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null) => Promise<void>;
    hasSearchQuery: () => boolean;
    filterSettings: () => void;
}

interface ExternalAccountsManagerDependencies {
    host: ExternalAccountsManagerHost;
}

export type { ExternalAccountsManagerDependencies, ExternalAccountsManagerHost, FormMode };
