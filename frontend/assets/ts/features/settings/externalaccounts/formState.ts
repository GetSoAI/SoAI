/* SoAI - Settings feature form state [frontend/assets/ts/features/settings/externalaccounts/formState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readNamedFormFieldTrimmedValue, requireNamedFormField, setNamedFormFieldValue, type NamedFormFieldHost } from '@core/dom/formFields.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatNullableJsonFormValue } from '@core/serialization/jsonForm.ts';
import { securityApi } from '@core/security/public.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import type { CalendarAccountEntry, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';

const createExternalAccountFormHost = (form: HTMLFormElement): NamedFormFieldHost => ({
    root: form,
    context: 'External accounts'
});

const createExternalAccountOauthFormHost = (form: HTMLFormElement, type: 'mail' | 'calendar'): NamedFormFieldHost => {
    const section = dom.resolve(`.external-accounts-auth-section--${type}`, form);
    if (!(section instanceof HTMLElement)) {
        throw new Error(`External accounts ${type} OAuth section is required`);
    }
    return {
        root: section,
        context: `External accounts ${type} OAuth`
    };
};

const optionalNumberValue = (value: number | null | undefined): string => {
    return typeof value === 'number' ? String(value) : '';
};

const setOauthFieldValues = (host: NamedFormFieldHost, account: MailAccountEntry | CalendarAccountEntry | null): void => {
    setNamedFormFieldValue(host, 'oauth_resource_metadata_url', account?.auth.oauth.resourceMetadataUrl ?? '');
    setNamedFormFieldValue(host, 'oauth_client_id', account?.auth.oauth.clientId ?? '');
    setNamedFormFieldValue(host, 'oauth_client_secret', '');
    setNamedFormFieldValue(host, 'oauth_scopes', account?.auth.oauth.scopes.join('\n') ?? '');
    setNamedFormFieldValue(host, 'oauth_required_scopes', account?.auth.oauth.requiredScopes.join('\n') ?? '');
    setNamedFormFieldValue(host, 'oauth_auth_server_issuer', account?.auth.oauth.authServerIssuer ?? '');
    setNamedFormFieldValue(host, 'oauth_authorization_endpoint', account?.auth.oauth.authorizationEndpoint ?? '');
    setNamedFormFieldValue(host, 'oauth_token_endpoint', account?.auth.oauth.tokenEndpoint ?? '');
    setNamedFormFieldValue(host, 'oauth_registration_endpoint', account?.auth.oauth.registrationEndpoint ?? '');
    setNamedFormFieldValue(host, 'oauth_token_endpoint_auth_method', account?.auth.oauth.tokenEndpointAuthMethod ?? '');
};

const setSharedFormValues = (host: NamedFormFieldHost, account: MailAccountEntry | CalendarAccountEntry | null): void => {
    setNamedFormFieldValue(host, 'label', account?.label ?? '');
    setNamedFormFieldValue(host, 'username', account?.username ?? '');
    setNamedFormFieldValue(host, 'auth_type', account?.auth.type ?? 'password');
    setNamedFormFieldValue(host, 'password', '');
};

const applyAuthVisibility = (form: HTMLFormElement, type: 'mail' | 'calendar'): void => {
    const host = createExternalAccountFormHost(form);
    const authType = readNamedFormFieldTrimmedValue(host, 'auth_type');
    dom.resolveAll(`.external-accounts-auth-field--${type}.external-accounts-auth-field--password`, form).forEach((element) => {
        if (element instanceof HTMLElement) {
            setVisibilityState(element, authType === 'password', { mode: 'hiddenAttribute' });
        }
    });
    dom.resolveAll(`.external-accounts-auth-field--${type}.external-accounts-auth-field--oauth`, form).forEach((element) => {
        if (element instanceof HTMLElement) {
            setVisibilityState(element, authType === 'oauth2', { mode: 'hiddenAttribute' });
        }
    });
    dom.resolveAll(`.external-accounts-auth-section--${type}`, form).forEach((element) => {
        if (element instanceof HTMLElement) {
            setVisibilityState(element, authType === 'oauth2', { mode: 'hiddenAttribute' });
        }
    });
};

const supportsLinkedMailAccount = (account: MailAccountEntry): boolean => {
    return account.supportedActions.includes('compose');
};

const resolveUnavailableLinkedMailLabel = (account: MailAccountEntry | null, selectedId: string): string => {
    const label = account?.label ?? selectedId;
    return `${label} (${i18n.t('common.notAvailable')})`;
};

const populateLinkedMailOptions = (form: HTMLFormElement, mailAccounts: MailAccountEntry[], selectedId: string | null): void => {
    const host = createExternalAccountFormHost(form);
    const select = requireNamedFormField(host, 'linked_mail_account_id');
    if (!(select instanceof HTMLSelectElement)) {
        throw new Error('Linked mail account field is invalid');
    }
    const selectableAccounts = mailAccounts.filter((account) => supportsLinkedMailAccount(account));
    const selectedAccount = selectedId !== null ? (mailAccounts.find((account) => account.accountId === selectedId) ?? null) : null;
    const options = [`<option value="">${securityApi.escapeHtml(i18n.t('common.none'))}</option>`]
        .concat(selectableAccounts.map((account) => `<option value="${securityApi.escapeAttribute(account.accountId)}">${securityApi.escapeHtml(account.label)}</option>`))
        .concat(selectedId !== null && !selectableAccounts.some((account) => account.accountId === selectedId) ? [`<option value="${securityApi.escapeAttribute(selectedId)}">${securityApi.escapeHtml(resolveUnavailableLinkedMailLabel(selectedAccount, selectedId))}</option>`] : [])
        .join('');
    replaceChildrenFromHtml({
        element: select,
        html: securityApi.sanitizeHtml(options),
        context: select
    });
    select.value = selectedId ?? '';
};

const applyMailFormState = (form: HTMLFormElement, account: MailAccountEntry | null): void => {
    const host = createExternalAccountFormHost(form);
    setSharedFormValues(host, account);
    setOauthFieldValues(createExternalAccountOauthFormHost(form, 'mail'), account);
    setNamedFormFieldValue(host, 'protocol', account?.transport.protocol ?? 'imap');
    setNamedFormFieldValue(host, 'inbound_host', account?.transport.inbound.host ?? '');
    setNamedFormFieldValue(host, 'inbound_port', optionalNumberValue(account?.transport.inbound.port));
    setNamedFormFieldValue(host, 'inbound_security', account?.transport.inbound.security ?? 'tls');
    setNamedFormFieldValue(host, 'smtp_host', account?.transport.outbound.host ?? '');
    setNamedFormFieldValue(host, 'smtp_port', optionalNumberValue(account?.transport.outbound.port));
    setNamedFormFieldValue(host, 'smtp_security', account?.transport.outbound.security ?? 'tls');
    setNamedFormFieldValue(host, 'folder_mapping', formatNullableJsonFormValue(account?.transport.folderMapping));
    applyAuthVisibility(form, 'mail');
};

const applyCalendarFormState = (form: HTMLFormElement, account: CalendarAccountEntry | null, mailAccounts: MailAccountEntry[]): void => {
    const host = createExternalAccountFormHost(form);
    setSharedFormValues(host, account);
    setOauthFieldValues(createExternalAccountOauthFormHost(form, 'calendar'), account);
    setNamedFormFieldValue(host, 'caldav_base_url', account?.transport.caldavBaseUrl ?? '');
    populateLinkedMailOptions(form, mailAccounts, account?.transport.linkedMailAccountId ?? null);
    setNamedFormFieldValue(host, 'discovered_principal', formatNullableJsonFormValue(account?.transport.discoveredPrincipal));
    applyAuthVisibility(form, 'calendar');
};

export { applyAuthVisibility, applyCalendarFormState, applyMailFormState, createExternalAccountFormHost, populateLinkedMailOptions };
