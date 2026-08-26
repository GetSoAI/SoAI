/* SoAI - Settings feature forms [frontend/assets/ts/features/settings/externalaccounts/forms.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readNamedFormFieldTrimmedValue } from '@core/dom/formFields.ts';
import { i18n } from '@core/i18n/index.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import type { CalendarAccountEntry, CalendarAccountTransportWrite, CalendarAccountWriteRequest, ExternalAccountAuthWrite, ExternalAccountWriteRequest, MailAccountEntry, MailAccountTransportWrite, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import { applyAuthVisibility, applyCalendarFormState, applyMailFormState, createExternalAccountFormHost, populateLinkedMailOptions } from '@features/settings/externalaccounts/formState.ts';
import { didCalendarTransportChange, didMailTransportChange, didOauthSettingsChange, maybeResetOauthState, readOauthPayload } from '@features/settings/externalaccounts/oauthPayload.ts';
import { buildCalendarTransportPayload, buildMailTransportPayload } from '@features/settings/externalaccounts/transportPayloads.ts';
import type { FormMode } from '@features/settings/externalaccounts/types.ts';
import { requireAuthType } from '@features/settings/externalaccounts/valueParsing.ts';

const buildExternalAccountAuthPayload = (inputArguments: { authType: 'password' | 'oauth2'; mode: FormMode; currentAccount: MailAccountEntry | CalendarAccountEntry | null; transportChanged: boolean; readTrimmed: (name: string) => string }): ExternalAccountAuthWrite => {
    const authPayload: ExternalAccountAuthWrite = { type: inputArguments.authType };
    const password = inputArguments.readTrimmed('password');
    if (inputArguments.authType === 'password') {
        if (inputArguments.mode === 'create' || inputArguments.currentAccount?.auth.type !== 'password') {
            authPayload.password = readRequiredTrimmedStringMessageValue(password, i18n.t('settings.externalAccounts.validation.password'));
        } else if (password) {
            authPayload.password = password;
        }
        return authPayload;
    }
    const oauthPayload = readOauthPayload(inputArguments.readTrimmed);
    const clientSecret = inputArguments.readTrimmed('oauth_client_secret');
    if (clientSecret || inputArguments.mode === 'create') {
        oauthPayload.clientSecret = clientSecret || null;
    }
    const changed =
        inputArguments.mode === 'create' ||
        didOauthSettingsChange(
            inputArguments.currentAccount,
            {
                username: inputArguments.readTrimmed('username'),
                ...oauthPayload
            },
            inputArguments.transportChanged,
            clientSecret
        );
    maybeResetOauthState(oauthPayload, inputArguments.authType, changed);
    authPayload.oauth = oauthPayload;
    return authPayload;
};

const buildExternalAccountPayload = <Account extends MailAccountEntry | CalendarAccountEntry, Transport>(inputArguments: { form: HTMLFormElement; mode: FormMode; currentAccount: Account | null; buildTransportPayload: (readTrimmed: (name: string) => string) => Transport; didTransportChange: (currentAccount: Account | null, transportPayload: Transport) => boolean }): ExternalAccountWriteRequest<Transport> => {
    const formHost = createExternalAccountFormHost(inputArguments.form);
    const readTrimmed = (name: string): string => readNamedFormFieldTrimmedValue(formHost, name);
    const transportPayload = inputArguments.buildTransportPayload(readTrimmed);
    return {
        label: readRequiredTrimmedStringMessageValue(readTrimmed('label'), i18n.t('settings.externalAccounts.validation.label')),
        username: readRequiredTrimmedStringMessageValue(readTrimmed('username'), i18n.t('settings.externalAccounts.validation.username')),
        auth: buildExternalAccountAuthPayload({
            authType: requireAuthType(readTrimmed('auth_type')),
            mode: inputArguments.mode,
            currentAccount: inputArguments.currentAccount,
            transportChanged: inputArguments.didTransportChange(inputArguments.currentAccount, transportPayload),
            readTrimmed
        }),
        transport: transportPayload
    };
};

const buildMailAccountPayload = (inputArguments: { form: HTMLFormElement; mode: FormMode; currentAccount: MailAccountEntry | null }): MailAccountWriteRequest => {
    return buildExternalAccountPayload<MailAccountEntry, MailAccountTransportWrite>({
        ...inputArguments,
        buildTransportPayload: buildMailTransportPayload,
        didTransportChange: didMailTransportChange
    });
};

const buildCalendarAccountPayload = (inputArguments: { form: HTMLFormElement; mode: FormMode; currentAccount: CalendarAccountEntry | null }): CalendarAccountWriteRequest => {
    return buildExternalAccountPayload<CalendarAccountEntry, CalendarAccountTransportWrite>({
        ...inputArguments,
        buildTransportPayload: buildCalendarTransportPayload,
        didTransportChange: didCalendarTransportChange
    });
};

export { applyAuthVisibility, applyCalendarFormState, applyMailFormState, buildCalendarAccountPayload, buildMailAccountPayload, populateLinkedMailOptions };
