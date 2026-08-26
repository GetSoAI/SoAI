/* SoAI - Settings feature mutations [frontend/assets/ts/features/settings/externalaccounts/mutations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { CalendarAccountEntry, CalendarAccountWriteRequest, ExternalAccountType, MailAccountEntry, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import { runExternalAccountConnectivityTest, runExternalAccountOauthClear, runExternalAccountOauthConnect, runExternalAccountSync } from '@features/settings/externalaccounts/actions.ts';
import type { ExternalAccountDescriptor } from '@features/settings/externalaccounts/descriptors.ts';
import { resolveExternalAccountOauthFailureMessage } from '@features/settings/externalaccounts/oauthPresentation.ts';
import type { ExternalAccountsManagerHost, FormMode } from '@features/settings/externalaccounts/types.ts';

type ExternalAccountEntry = MailAccountEntry | CalendarAccountEntry;
type ExternalAccountDescriptorAny = ExternalAccountDescriptor<'mail', MailAccountEntry, MailAccountWriteRequest> | ExternalAccountDescriptor<'calendar', CalendarAccountEntry, CalendarAccountWriteRequest>;

interface PersistExternalAccountArguments<AccountType extends ExternalAccountType, Account extends ExternalAccountEntry, WriteRequest> {
    descriptor: ExternalAccountDescriptor<AccountType, Account, WriteRequest>;
    host: ExternalAccountsManagerHost;
    form: HTMLFormElement;
    mode: FormMode;
    currentAccount: Account | null;
}

const persistExternalAccount = async <AccountType extends ExternalAccountType, Account extends ExternalAccountEntry, WriteRequest>(inputArguments: PersistExternalAccountArguments<AccountType, Account, WriteRequest>): Promise<{ account: Account; successMessage: string }> => {
    const payload = inputArguments.descriptor.buildPayload({
        form: inputArguments.form,
        mode: inputArguments.mode,
        currentAccount: inputArguments.currentAccount
    });
    const api = inputArguments.descriptor.api(inputArguments.host);
    const response =
        inputArguments.mode === 'create'
            ? await inputArguments.host.runWithBoundary(`settings:create${capitalize(inputArguments.descriptor.type)}ExternalAccount`, async () => await api.create(payload))
            : await inputArguments.host.runWithBoundary(`settings:update${capitalize(inputArguments.descriptor.type)}ExternalAccount`, async () => {
                  const accountId = inputArguments.currentAccount?.accountId ?? null;
                  if (accountId === null) {
                      throw new Error(i18n.t('settings.externalAccounts.errors.saveFailed'));
                  }
                  return await api.update(accountId, payload);
              });
    return {
        account: response,
        successMessage: inputArguments.mode === 'create' ? inputArguments.descriptor.messages.createSuccess() : inputArguments.descriptor.messages.updateSuccess()
    };
};

const runExternalAccountAction = async (host: ExternalAccountsManagerHost, descriptor: ExternalAccountDescriptorAny, accountId: string, action: 'test' | 'sync' | 'oauth_connect' | 'oauth_clear'): Promise<string> => {
    if (action === 'test') {
        await runExternalAccountConnectivityTest(host, descriptor.type, accountId);
        return descriptor.messages.testSuccess();
    }
    if (action === 'sync') {
        await runExternalAccountSync(host, descriptor.type, accountId);
        return descriptor.messages.syncSuccess();
    }
    if (action === 'oauth_clear') {
        await runExternalAccountOauthClear(host, descriptor.type, accountId);
        return descriptor.messages.oauthClearSuccess();
    }
    const popupResult = await runExternalAccountOauthConnect(host, descriptor.type, accountId);
    if (!popupResult.ok) {
        throw new Error(resolveExternalAccountOauthFailureMessage(descriptor.messages.oauthFailed(), popupResult.oauthStatus));
    }
    return descriptor.messages.oauthConnectSuccess();
};

const capitalize = (value: string): string => {
    return value.slice(0, 1).toUpperCase() + value.slice(1);
};

export { persistExternalAccount, runExternalAccountAction };
