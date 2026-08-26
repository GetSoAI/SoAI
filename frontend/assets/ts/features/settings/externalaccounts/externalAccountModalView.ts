/* SoAI - Settings feature external account modal view [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldLabelHtml } from '@core/ui/forms/requiredMarker.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { EXTERNAL_ACCOUNT_MODAL_ACTION_BACK, EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_CALENDAR, EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_MAIL, EXTERNAL_ACCOUNT_MODAL_ACTION_DELETE, EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CLEAR, EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CONNECT, EXTERNAL_ACCOUNT_MODAL_ACTION_SAVE, EXTERNAL_ACCOUNT_MODAL_ACTION_SYNC, EXTERNAL_ACCOUNT_MODAL_ACTION_TEST } from '@features/settings/externalaccounts/actionIds.ts';

const renderInput = (inputArguments: { id: string; name: string; type?: string; placeholder?: string; secret?: boolean | undefined }): string => {
    const type = inputArguments.secret === true ? resolveSecretInputType() : (inputArguments.type ?? 'text');
    const placeholder = inputArguments.placeholder ? ` placeholder="${uiAttr(inputArguments.placeholder).html}"` : '';
    const className = inputArguments.secret === true ? 'setting-input setting-input--wide setting-input--full secret-input' : 'setting-input setting-input--wide setting-input--full';
    const input = `<input id="${uiAttr(inputArguments.id).html}" class="${className}" name="${uiAttr(inputArguments.name).html}" type="${uiAttr(type).html}"${placeholder} autocomplete="off">`;
    return inputArguments.secret === true ? renderSecretInputControl({ inputId: inputArguments.id, inputMarkup: input }) : input;
};

const renderTextarea = (inputArguments: { id: string; name: string; placeholder?: string; rows?: number }): string => {
    const placeholder = inputArguments.placeholder ? ` placeholder="${uiAttr(inputArguments.placeholder).html}"` : '';
    const rows = inputArguments.rows ?? 4;
    return `<textarea id="${uiAttr(inputArguments.id).html}" class="setting-textarea setting-textarea--wide setting-input--full external-accounts-textarea" name="${uiAttr(inputArguments.name).html}" rows="${uiAttr(rows).html}"${placeholder}></textarea>`;
};

const renderSelect = (inputArguments: { id: string; name: string; options: ReadonlyArray<{ value: string; label: string }> }): string => {
    return renderStandardDropdownSelectControl(`<select id="${uiAttr(inputArguments.id).html}" class="setting-input setting-input--wide setting-input--full" name="${uiAttr(inputArguments.name).html}">${inputArguments.options.map((option) => `<option value="${uiAttr(option.value).html}">${uiAttr(option.label).html}</option>`).join('')}</select>`);
};

const renderRequiredLabel = (label: string): string => {
    return renderRequiredFieldLabelHtml(label);
};

const renderLauncherItem = (inputArguments: { type: 'mail' | 'calendar'; title: string; description: string; actionId: string; itemId: string }): string => {
    const iconName = inputArguments.type === 'mail' ? 'mail' : 'calendar';
    const iconMarkup = renderIconSlot(getIconSync(iconName, { size: 24, strokeWidth: 1.5 }), { className: 'external-account-modal__launcher-icon settings-card-surface' });
    const interactiveLabel = `${inputArguments.title}. ${inputArguments.description}`;
    return `<div id="${uiAttr(inputArguments.itemId).html}" class="setting-item external-account-modal__launcher-item" role="button" tabindex="0" aria-pressed="false" aria-label="${uiAttr(interactiveLabel).html}" data-tooltip="${uiAttr(inputArguments.title).html}" data-action="${uiAttr(inputArguments.actionId).html}"><div class="setting-info">${iconMarkup}<label class="setting-label">${uiAttr(inputArguments.title).html}</label><span class="setting-help">${uiAttr(inputArguments.description).html}</span></div></div>`;
};

const renderLauncherSection = (modalId: string): string => {
    return renderSettingsSubgroup({
        title: i18n.t('settings.externalAccounts.modal.launcherTitle'),
        description: i18n.t('settings.externalAccounts.modal.launcherDescription'),
        className: 'external-account-modal__launcher',
        tagName: 'section',
        attributes: { id: modalUiId(modalId, 'launcher') },
        content: renderSettingsGroup([
            renderLauncherItem({
                type: 'mail',
                title: i18n.t('settings.externalAccounts.modal.mailChoiceTitle'),
                description: i18n.t('settings.externalAccounts.modal.mailChoiceDescription'),
                actionId: EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_MAIL,
                itemId: modalUiId(modalId, 'choose-mail')
            }),
            renderLauncherItem({
                type: 'calendar',
                title: i18n.t('settings.externalAccounts.modal.calendarChoiceTitle'),
                description: i18n.t('settings.externalAccounts.modal.calendarChoiceDescription'),
                actionId: EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_CALENDAR,
                itemId: modalUiId(modalId, 'choose-calendar')
            })
        ])
    });
};

const renderOauthFields = (modalId: string, prefix: 'mail' | 'calendar'): string => {
    const scopePlaceholder = i18n.t('settings.externalAccounts.shared.oauth.scopesPlaceholder');
    return renderSettingsGroup([
        renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.shared.oauth.resourceMetadataUrl')), help: i18n.t('settings.externalAccounts.shared.oauth.resourceMetadataHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-resource-metadata-url`), name: 'oauth_resource_metadata_url', type: 'url', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.resourceMetadataUrl') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.clientId'), help: i18n.t('settings.externalAccounts.shared.oauth.clientIdHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-client-id`), name: 'oauth_client_id', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.clientId') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.clientSecret'), help: i18n.t('settings.externalAccounts.shared.oauth.clientSecretHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-client-secret`), name: 'oauth_client_secret', secret: true }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.scopes'), help: i18n.t('settings.externalAccounts.shared.oauth.scopesHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderTextarea({ id: modalUiId(modalId, `${prefix}-oauth-scopes`), name: 'oauth_scopes', rows: 3, placeholder: scopePlaceholder }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.requiredScopes'), help: i18n.t('settings.externalAccounts.shared.oauth.requiredScopesHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderTextarea({ id: modalUiId(modalId, `${prefix}-oauth-required-scopes`), name: 'oauth_required_scopes', rows: 3, placeholder: scopePlaceholder }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.issuer'), help: i18n.t('settings.externalAccounts.shared.oauth.issuerHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-issuer`), name: 'oauth_auth_server_issuer', type: 'url', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.issuer') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.authorizationEndpoint'), help: i18n.t('settings.externalAccounts.shared.oauth.authorizationEndpointHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-authorization-endpoint`), name: 'oauth_authorization_endpoint', type: 'url', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.authorizationEndpoint') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.tokenEndpoint'), help: i18n.t('settings.externalAccounts.shared.oauth.tokenEndpointHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-token-endpoint`), name: 'oauth_token_endpoint', type: 'url', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.tokenEndpoint') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.registrationEndpoint'), help: i18n.t('settings.externalAccounts.shared.oauth.registrationEndpointHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-registration-endpoint`), name: 'oauth_registration_endpoint', type: 'url', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.registrationEndpoint') }) }),
        renderSettingItem({ label: i18n.t('settings.externalAccounts.shared.oauth.tokenEndpointAuthMethod'), help: i18n.t('settings.externalAccounts.shared.oauth.tokenEndpointAuthMethodHelp'), className: `external-accounts-auth-field external-accounts-auth-field--oauth external-accounts-auth-field--${prefix}`, control: renderInput({ id: modalUiId(modalId, `${prefix}-oauth-token-auth-method`), name: 'oauth_token_endpoint_auth_method', placeholder: i18n.t('settings.externalAccounts.shared.oauth.placeholders.tokenEndpointAuthMethod') }) })
    ]);
};

const renderSharedSection = (modalId: string): string => {
    const authOptions = [
        { value: 'password', label: i18n.t('settings.externalAccounts.shared.auth.password') },
        { value: 'oauth2', label: i18n.t('settings.externalAccounts.shared.auth.oauth2') }
    ];
    return renderSettingsSubgroup({
        title: i18n.t('settings.externalAccounts.modal.identityTitle'),
        description: i18n.t('settings.externalAccounts.modal.identityDescription'),
        className: 'external-account-modal__group',
        tagName: 'section',
        content: renderSettingsGroup([
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.shared.label')), help: i18n.t('settings.externalAccounts.shared.labelHelp'), control: renderInput({ id: modalUiId(modalId, 'label'), name: 'label', placeholder: i18n.t('settings.externalAccounts.shared.placeholders.label') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.shared.username')), help: i18n.t('settings.externalAccounts.shared.usernameHelp'), control: renderInput({ id: modalUiId(modalId, 'username'), name: 'username', placeholder: i18n.t('settings.externalAccounts.shared.placeholders.username') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.shared.authType')), help: i18n.t('settings.externalAccounts.shared.authTypeHelp'), control: renderSelect({ id: modalUiId(modalId, 'auth-type'), name: 'auth_type', options: authOptions }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.shared.password')), help: i18n.t('settings.externalAccounts.shared.passwordHelp'), className: 'external-accounts-auth-field external-accounts-auth-field--password external-accounts-auth-field--mail external-accounts-auth-field--calendar', control: renderInput({ id: modalUiId(modalId, 'password'), name: 'password', secret: true }) })
        ])
    });
};

const renderMailTransportSection = (modalId: string): string => {
    const protocolOptions = [
        { value: 'imap', label: i18n.t('settings.externalAccounts.mail.protocolOptions.imap') },
        { value: 'pop3', label: i18n.t('settings.externalAccounts.mail.protocolOptions.pop3') }
    ];
    const securityOptions = [
        { value: 'tls', label: i18n.t('settings.externalAccounts.shared.security.tls') },
        { value: 'starttls', label: i18n.t('settings.externalAccounts.shared.security.starttls') }
    ];
    return renderSettingsSubgroup({
        title: i18n.t('settings.externalAccounts.modal.mailTransportTitle'),
        description: i18n.t('settings.externalAccounts.mail.form.description'),
        className: 'external-account-modal__group',
        tagName: 'section',
        attributes: { id: modalUiId(modalId, 'mail-section'), hidden: true },
        content: renderSettingsGroup([
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.protocol')), help: i18n.t('settings.externalAccounts.mail.protocolHelp'), control: renderSelect({ id: modalUiId(modalId, 'mail-protocol'), name: 'protocol', options: protocolOptions }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.inboundHost')), help: i18n.t('settings.externalAccounts.mail.inboundHostHelp'), control: renderInput({ id: modalUiId(modalId, 'mail-inbound-host'), name: 'inbound_host', placeholder: i18n.t('settings.externalAccounts.mail.placeholders.inboundHost') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.inboundPort')), help: i18n.t('settings.externalAccounts.mail.inboundPortHelp'), control: renderInput({ id: modalUiId(modalId, 'mail-inbound-port'), name: 'inbound_port', type: 'number', placeholder: i18n.t('settings.externalAccounts.mail.placeholders.inboundPort') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.inboundSecurity')), help: i18n.t('settings.externalAccounts.mail.inboundSecurityHelp'), control: renderSelect({ id: modalUiId(modalId, 'mail-inbound-security'), name: 'inbound_security', options: securityOptions }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.smtpHost')), help: i18n.t('settings.externalAccounts.mail.smtpHostHelp'), control: renderInput({ id: modalUiId(modalId, 'mail-smtp-host'), name: 'smtp_host', placeholder: i18n.t('settings.externalAccounts.mail.placeholders.smtpHost') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.smtpPort')), help: i18n.t('settings.externalAccounts.mail.smtpPortHelp'), control: renderInput({ id: modalUiId(modalId, 'mail-smtp-port'), name: 'smtp_port', type: 'number', placeholder: i18n.t('settings.externalAccounts.mail.placeholders.smtpPort') }) }),
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.mail.smtpSecurity')), help: i18n.t('settings.externalAccounts.mail.smtpSecurityHelp'), control: renderSelect({ id: modalUiId(modalId, 'mail-smtp-security'), name: 'smtp_security', options: securityOptions }) }),
            renderSettingItem({ label: i18n.t('settings.externalAccounts.mail.folderMapping'), help: i18n.t('settings.externalAccounts.mail.folderMappingHelp'), control: renderTextarea({ id: modalUiId(modalId, 'mail-folder-mapping'), name: 'folder_mapping', rows: 4, placeholder: i18n.t('settings.externalAccounts.mail.folderMappingPlaceholder') }) })
        ])
    });
};

const renderCalendarTransportSection = (modalId: string): string => {
    return renderSettingsSubgroup({
        title: i18n.t('settings.externalAccounts.modal.calendarTransportTitle'),
        description: i18n.t('settings.externalAccounts.calendar.form.description'),
        className: 'external-account-modal__group',
        tagName: 'section',
        attributes: { id: modalUiId(modalId, 'calendar-section'), hidden: true },
        content: renderSettingsGroup([
            renderSettingItem({ label: renderRequiredLabel(i18n.t('settings.externalAccounts.calendar.caldavBaseUrl')), help: i18n.t('settings.externalAccounts.calendar.caldavBaseUrlHelp'), control: renderInput({ id: modalUiId(modalId, 'calendar-caldav-base-url'), name: 'caldav_base_url', type: 'url', placeholder: i18n.t('settings.externalAccounts.calendar.placeholders.caldavBaseUrl') }) }),
            renderSettingItem({ label: i18n.t('settings.externalAccounts.calendar.linkedMailAccount'), help: i18n.t('settings.externalAccounts.calendar.linkedMailHelp'), control: renderStandardDropdownSelectControl(`<select id="${uiAttr(modalUiId(modalId, 'calendar-linked-mail-account')).html}" class="setting-input setting-input--wide setting-input--full" name="linked_mail_account_id"></select>`) }),
            renderSettingItem({ label: i18n.t('settings.externalAccounts.calendar.discoveredPrincipal'), help: i18n.t('settings.externalAccounts.calendar.discoveredPrincipalHelp'), control: renderTextarea({ id: modalUiId(modalId, 'calendar-discovered-principal'), name: 'discovered_principal', rows: 4, placeholder: '{"href":"https://..."}' }) })
        ])
    });
};

const renderOauthSection = (modalId: string, prefix: 'mail' | 'calendar'): string => {
    return renderSettingsSubgroup({
        title: i18n.t('settings.externalAccounts.modal.oauthTitle'),
        description: i18n.t('settings.externalAccounts.modal.oauthDescription'),
        className: `external-account-modal__group external-accounts-auth-section external-accounts-auth-section--${prefix}`,
        tagName: 'section',
        attributes: { id: modalUiId(modalId, `${prefix}-oauth-section`), hidden: true },
        content: renderOauthFields(modalId, prefix)
    });
};

const renderEditorHeaderSection = (modalId: string): string => {
    return `<section id="${uiAttr(modalUiId(modalId, 'editor-header')).html}" class="settings-subgroup external-account-modal__editor-header"><div class="subgroup-header"><div><h3 id="${uiAttr(modalUiId(modalId, 'editor-title')).html}" class="subgroup-title"></h3><p id="${uiAttr(modalUiId(modalId, 'editor-description')).html}" class="external-account-modal__subgroup-description"></p></div></div><div id="${uiAttr(modalUiId(modalId, 'summary')).html}" class="external-account-modal__summary settings-card-surface" hidden></div><div id="${uiAttr(modalUiId(modalId, 'status')).html}" class="form-help external-account-modal__surface settings-card-surface" role="status" aria-live="polite" aria-atomic="true" hidden></div><div id="${uiAttr(modalUiId(modalId, 'error')).html}" class="form-help external-account-modal__surface external-account-modal__surface--error settings-card-surface" role="alert" aria-live="assertive" aria-atomic="true" hidden></div></section>`;
};

const buildFormMarkup = (modalId: string): string => {
    return `${renderLauncherSection(modalId)}<div id="${uiAttr(modalUiId(modalId, 'editor')).html}" class="external-account-modal__editor" hidden>${renderEditorHeaderSection(modalId)}<form id="${uiAttr(modalUiId(modalId, 'form')).html}" class="external-account-modal__form" novalidate>${renderSharedSection(modalId)}${renderMailTransportSection(modalId)}${renderCalendarTransportSection(modalId)}${renderOauthSection(modalId, 'mail')}${renderOauthSection(modalId, 'calendar')}</form></div>`;
};

const createExternalAccountModalElement = (modalId: string): HTMLElement => {
    const header = renderStandardModalHeader({ modalId, title: i18n.t('settings.externalAccounts.modal.defaultTitle'), description: i18n.t('common.modalDescriptions.settingsExternalAccounts'), titleId: modalUiId(modalId, 'title') });
    const body = renderModalBody(toTrustedUiHtml(buildFormMarkup(modalId)), { className: 'external-account-modal__body' });
    const leftButtons = toTrustedUiHtml([renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, 'close-btn'), text: i18n.t('common.close') }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'back-btn'), text: i18n.t('common.back'), variant: 'neutral', action: EXTERNAL_ACCOUNT_MODAL_ACTION_BACK, attributes: { hidden: true } }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'oauth-connect-btn'), text: i18n.t('settings.externalAccounts.shared.actions.connectOauth'), variant: 'neutral', action: EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CONNECT, attributes: { hidden: true } }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'oauth-clear-btn'), text: i18n.t('settings.externalAccounts.shared.actions.clearOauth'), variant: 'neutral', action: EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CLEAR, attributes: { hidden: true } }).html].join(''));
    const rightButtons = toTrustedUiHtml([renderModalFooterActionButton({ id: modalUiId(modalId, 'delete-btn'), text: i18n.t('common.delete'), variant: 'danger', action: EXTERNAL_ACCOUNT_MODAL_ACTION_DELETE, attributes: { hidden: true } }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'test-btn'), text: i18n.t('settings.externalAccounts.shared.actions.test'), variant: 'primary', action: EXTERNAL_ACCOUNT_MODAL_ACTION_TEST, attributes: { hidden: true } }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'sync-btn'), text: i18n.t('settings.externalAccounts.shared.actions.syncNow'), variant: 'neutral', action: EXTERNAL_ACCOUNT_MODAL_ACTION_SYNC, attributes: { hidden: true } }).html, renderModalFooterActionButton({ id: modalUiId(modalId, 'save-btn'), text: i18n.t('settings.externalAccounts.shared.actions.add'), variant: 'accent', action: EXTERNAL_ACCOUNT_MODAL_ACTION_SAVE }).html].join(''));
    const footer = renderSplitModalFooter({ left: leftButtons, right: rightButtons, className: 'external-account-modal__footer' });
    return createModalElement({ id: modalId, className: 'external-account-modal', labelledBy: modalUiId(modalId, 'title'), rootAttributes: { 'data-page-scope': 'settings' }, header, body, footer });
};

export { createExternalAccountModalElement };
