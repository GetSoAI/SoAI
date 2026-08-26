/* SoAI - Settings feature external accounts actions [frontend/assets/ts/features/settings/externalaccounts/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { CalendarAccountEntry, CalendarAccountWriteRequest, ExternalAccountActionResponse, ExternalAccountType, MailAccountEntry, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsEndpoints } from '@core/api/endpoints/webuiExternalAccounts.ts';
import type { ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';
import { openOauthPopupAndWait, type OAuthPopupResult } from '@features/settings/oauthPopupFlowController.ts';

type ExternalAccountsApi = ExternalAccountsEndpoints<MailAccountEntry, MailAccountWriteRequest> | ExternalAccountsEndpoints<CalendarAccountEntry, CalendarAccountWriteRequest>;

const resolveAccountsApi = (host: ExternalAccountsManagerHost, accountType: ExternalAccountType): ExternalAccountsApi =>
    ({
        mail: host.api.webui.mail.accounts,
        calendar: host.api.webui.calendar.accounts
    })[accountType];

const runAccountAction = async (host: ExternalAccountsManagerHost, accountType: ExternalAccountType, boundaryName: string, action: (api: ExternalAccountsApi) => Promise<ExternalAccountActionResponse>): Promise<ExternalAccountActionResponse> => {
    const api = resolveAccountsApi(host, accountType);
    return await host.runWithBoundary(boundaryName, async () => await action(api));
};

const runExternalAccountConnectivityTest = async (host: ExternalAccountsManagerHost, accountType: ExternalAccountType, accountId: string): Promise<void> => {
    await runAccountAction(host, accountType, `settings:test:${accountType}ExternalAccount`, async (api) => await api.test(accountId));
};

const runExternalAccountSync = async (host: ExternalAccountsManagerHost, accountType: ExternalAccountType, accountId: string): Promise<void> => {
    await runAccountAction(host, accountType, `settings:sync:${accountType}ExternalAccount`, async (api) => await api.sync(accountId));
};

const runExternalAccountOauthConnect = async (host: ExternalAccountsManagerHost, accountType: ExternalAccountType, accountId: string): Promise<OAuthPopupResult> => {
    const api = resolveAccountsApi(host, accountType);
    const response = await runAccountAction(host, accountType, `settings:oauthConnect:${accountType}ExternalAccount`, async () => await api.oauth.start(accountId));
    if (response.redirectUrl === null) {
        throw new Error(i18n.t('settings.externalAccounts.errors.oauthStartFailed'));
    }
    return await openOauthPopupAndWait({
        redirectUrl: response.redirectUrl,
        pollStatus: async () => await api.oauth.status(accountId),
        logContext: 'ExternalAccountsActions',
        startFailureMessage: i18n.t('settings.externalAccounts.errors.oauthStartFailed'),
        statusFailureMessage: i18n.t('settings.externalAccounts.errors.actionFailed')
    });
};

const runExternalAccountOauthClear = async (host: ExternalAccountsManagerHost, accountType: ExternalAccountType, accountId: string): Promise<void> => {
    await runAccountAction(host, accountType, `settings:oauthClear:${accountType}ExternalAccount`, async (api) => await api.oauth.clear(accountId));
};

export { runExternalAccountConnectivityTest, runExternalAccountOauthClear, runExternalAccountOauthConnect, runExternalAccountSync };
