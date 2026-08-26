/* SoAI - Settings feature external account modal persistence [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalPersistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { CALENDAR_DESCRIPTOR, MAIL_DESCRIPTOR } from '@features/settings/externalaccounts/descriptors.ts';
import { persistExternalAccount } from '@features/settings/externalaccounts/mutations.ts';
import type { CalendarAccountEntry, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';

type ExternalAccountEntry = MailAccountEntry | CalendarAccountEntry;
type ExternalAccountType = 'mail' | 'calendar';
type ExternalAccountModalMode = 'launcher' | 'create' | 'edit';

const canBuildCurrentExternalAccountPayload = (inputArguments: { form: HTMLFormElement; mode: ExternalAccountModalMode; accountType: ExternalAccountType | null; currentAccount: ExternalAccountEntry | null }): boolean => {
    try {
        if (inputArguments.mode === 'launcher' || inputArguments.accountType === null) {
            return false;
        }
        if (inputArguments.accountType === 'mail') {
            MAIL_DESCRIPTOR.buildPayload({
                form: inputArguments.form,
                mode: inputArguments.mode,
                currentAccount: inputArguments.currentAccount?.accountType === 'mail' ? inputArguments.currentAccount : null
            });
        } else {
            CALENDAR_DESCRIPTOR.buildPayload({
                form: inputArguments.form,
                mode: inputArguments.mode,
                currentAccount: inputArguments.currentAccount?.accountType === 'calendar' ? inputArguments.currentAccount : null
            });
        }
        return true;
    } catch (error) {
        errorHandler.warn('ExternalAccountModalPersistence', 'Failed to validate current external account payload', ensureError(error));
        return false;
    }
};

const persistCurrentExternalAccount = async (inputArguments: { host: ExternalAccountsManagerHost; form: HTMLFormElement; mode: Exclude<ExternalAccountModalMode, 'launcher'>; accountType: ExternalAccountType; currentAccount: ExternalAccountEntry | null }): Promise<{ account: ExternalAccountEntry; successMessage: string }> => {
    if (inputArguments.accountType === 'mail') {
        return await persistExternalAccount({
            descriptor: MAIL_DESCRIPTOR,
            host: inputArguments.host,
            form: inputArguments.form,
            mode: inputArguments.mode,
            currentAccount: inputArguments.currentAccount?.accountType === 'mail' ? inputArguments.currentAccount : null
        });
    }
    return await persistExternalAccount({
        descriptor: CALENDAR_DESCRIPTOR,
        host: inputArguments.host,
        form: inputArguments.form,
        mode: inputArguments.mode,
        currentAccount: inputArguments.currentAccount?.accountType === 'calendar' ? inputArguments.currentAccount : null
    });
};

export { canBuildCurrentExternalAccountPayload, persistCurrentExternalAccount };
