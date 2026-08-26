/* SoAI - Settings feature external account modal state [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatNullableEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { buildNamedFormFieldSignature, setNamedFormFieldValues } from '@core/dom/formFields.ts';
import { setStatusSurface } from '@core/ui/statusSurface.ts';
import { createExternalAccountFormHost } from '@features/settings/externalaccounts/formState.ts';
import type { CalendarAccountEntry, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';

type ExternalAccountEntry = MailAccountEntry | CalendarAccountEntry;

const EXTERNAL_ACCOUNT_FIELD_NAMES: readonly string[] = Object.freeze(['label', 'username', 'auth_type', 'password', 'protocol', 'inbound_host', 'inbound_port', 'inbound_security', 'smtp_host', 'smtp_port', 'smtp_security', 'folder_mapping', 'caldav_base_url', 'linked_mail_account_id', 'discovered_principal', 'oauth_resource_metadata_url', 'oauth_client_id', 'oauth_client_secret', 'oauth_scopes', 'oauth_required_scopes', 'oauth_auth_server_issuer', 'oauth_authorization_endpoint', 'oauth_token_endpoint', 'oauth_registration_endpoint', 'oauth_token_endpoint_auth_method']);

const clearExternalAccountFormValues = (form: HTMLFormElement): void => {
    const host = createExternalAccountFormHost(form);
    EXTERNAL_ACCOUNT_FIELD_NAMES.forEach((name) => {
        setNamedFormFieldValues(host, name, '');
    });
};

const computeExternalAccountFormSnapshot = (form: HTMLFormElement): string => {
    return buildNamedFormFieldSignature(createExternalAccountFormHost(form), EXTERNAL_ACCOUNT_FIELD_NAMES);
};

const setExternalAccountSurface = (surface: HTMLElement, message: string | null, tone: 'success' | 'warning' | 'error' | 'info'): void => {
    setStatusSurface({
        surface,
        message,
        tone,
        visibility: 'hiddenAttribute'
    });
};

const resolveExternalAccountSummary = (account: ExternalAccountEntry | null): string => {
    if (account === null) {
        return '';
    }
    const syncText = account.sync.lastSyncError ? i18n.t('settings.externalAccounts.shared.syncError') : i18n.t('settings.externalAccounts.shared.lastSync');
    const syncValue = formatNullableEpochMsMinuteWithFallback(account.sync.lastSyncAtMs, i18n.t('common.notAvailable'));
    return `${account.label} · ${account.username ?? i18n.t('common.notAvailable')} · ${syncText}: ${syncValue}`;
};

export { clearExternalAccountFormValues, computeExternalAccountFormSnapshot, resolveExternalAccountSummary, setExternalAccountSurface };
