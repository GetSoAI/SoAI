/* SoAI - Messaging account editor markup [frontend/assets/ts/features/settings/messaging/modalView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderChatParameterEditorModalMarkup } from '@core/chat/parameters/parameterEditorModalMarkup.ts';
import { buildWorkspaceFolderFieldMarkup } from '@core/fileexplorerbrowser/workspaceFolderFieldMarkup.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildMcpConversationSettingsBodyMarkup } from '@core/mcp/conversationSettingsMarkup.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldLabelHtml } from '@core/ui/forms/requiredMarker.ts';
import { MESSAGING_MODAL_ACTION_MCP_GROUP_TOGGLE, MESSAGING_MODAL_ACTION_MCP_MODE_SELECT, MESSAGING_MODAL_ACTION_MCP_SEARCH, MESSAGING_MODAL_ACTION_MCP_SERVER_TOGGLE, MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE, MESSAGING_MODAL_ACTION_PARAMETERS, MESSAGING_MODAL_ACTION_SAVE, MESSAGING_MODAL_ACTION_WORKSPACE, SETTINGS_MESSAGING_PARAMETERS_MODAL_ID } from '@features/settings/messaging/constants.ts';
import { MESSAGING_PROVIDER_DESCRIPTORS } from '@features/settings/messaging/descriptors.ts';
import { resolveMessagingCredentialHelp, resolveMessagingCredentialLabel, resolveMessagingProviderDescription, resolveMessagingProviderTitle } from '@features/settings/messaging/labels.ts';

const renderToggle = (modalId: string, token: string, inputClassName: string, checked: boolean): string =>
    renderToggleSwitch({
        id: modalUiId(modalId, token),
        checked,
        labels: { trueLabel: i18n.t('common.enabled'), falseLabel: i18n.t('common.disabled') },
        inputClassName,
        wrapperTag: 'div'
    });

const renderInput = (id: string, type = 'text'): string => `<input id="${uiAttr(id).html}" class="setting-input setting-input--wide setting-input--full form-input" type="${uiAttr(type).html}" autocomplete="off">`;

const renderCredentialInput = (modalId: string, providerId: string, field: (typeof MESSAGING_PROVIDER_DESCRIPTORS)[number]['fields'][number]): string => {
    const pattern = field.pattern ? ` pattern="${uiAttr(field.pattern.source).html}"` : '';
    return `<input id="${uiAttr(modalUiId(modalId, `credential-${providerId}-${field.uiToken}`)).html}" class="setting-input setting-input--wide setting-input--full form-input messaging-credential-input" type="${uiAttr(field.inputType).html}" minlength="${String(field.minLength)}" maxlength="${String(field.maxLength)}"${pattern} autocomplete="off">`;
};

const renderSelect = (id: string, options: string): string => renderStandardDropdownSelectControl(`<select id="${uiAttr(id).html}" class="setting-input setting-input--wide setting-input--full form-input">${options}</select>`);

const renderIdentityGroup = (modalId: string): string => {
    const providers = MESSAGING_PROVIDER_DESCRIPTORS.map((descriptor) => `<option value="${uiAttr(descriptor.id).html}">${uiText(resolveMessagingProviderTitle(descriptor.id)).html}</option>`).join('');
    const locales = `<option value="en">${uiText(i18n.t('settings.messaging.editor.localeEnglish')).html}</option><option value="it">${uiText(i18n.t('settings.messaging.editor.localeItalian')).html}</option>`;
    return renderSettingsSubgroup({
        title: i18n.t('settings.messaging.editor.identityTitle'),
        description: i18n.t('settings.messaging.editor.identityDescription'),
        tagName: 'section',
        className: 'messaging-account-modal__group',
        content: renderSettingsGroup([
            renderSettingItem({
                label: renderRequiredFieldLabelHtml(i18n.t('settings.messaging.editor.label')),
                control: renderInput(modalUiId(modalId, 'label')),
                fieldKey: 'label'
            }),
            renderSettingItem({
                label: renderRequiredFieldLabelHtml(i18n.t('settings.messaging.editor.platform')),
                control: renderSelect(modalUiId(modalId, 'platform'), providers),
                fieldKey: 'platform'
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.locale'),
                control: renderSelect(modalUiId(modalId, 'locale'), locales),
                fieldKey: 'locale'
            })
        ])
    });
};

const renderCredentialGroup = (modalId: string): string => {
    const providerSections = MESSAGING_PROVIDER_DESCRIPTORS.map((descriptor) => {
        const fields = descriptor.fields.map((field) =>
            renderSettingItem({
                label: renderRequiredFieldLabelHtml(resolveMessagingCredentialLabel(descriptor.id, field.key)),
                help: resolveMessagingCredentialHelp(descriptor.id, field.key),
                className: 'messaging-account-modal__credential',
                fieldKey: `credential-${descriptor.id}-${field.uiToken}`,
                control: renderCredentialInput(modalId, descriptor.id, field)
            })
        );
        return `<section id="${uiAttr(modalUiId(modalId, `credentials-${descriptor.id}`)).html}" class="messaging-provider-credentials" data-platform="${uiAttr(descriptor.id).html}"><h4 class="messaging-provider-credentials__title">${uiText(resolveMessagingProviderTitle(descriptor.id)).html}</h4><p class="subgroup-description">${uiText(resolveMessagingProviderDescription(descriptor.id)).html}</p>${renderSettingsGroup(fields)}</section>`;
    }).join('');
    return renderSettingsSubgroup({
        title: i18n.t('settings.messaging.editor.credentialsTitle'),
        description: i18n.t('settings.messaging.editor.credentialsDescription'),
        tagName: 'section',
        className: 'messaging-account-modal__group',
        content: providerSections
    });
};

const renderAccessGroup = (modalId: string): string =>
    renderSettingsSubgroup({
        title: i18n.t('settings.messaging.editor.accessTitle'),
        description: i18n.t('settings.messaging.editor.accessDescription'),
        tagName: 'section',
        className: 'messaging-account-modal__group',
        content: renderSettingsGroup([
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.acceptMessagesFromAnyone'),
                help: i18n.t('settings.messaging.editor.acceptMessagesFromAnyoneHint'),
                fieldKey: 'accept-anyone',
                control: renderToggle(modalId, 'accept-anyone', 'messaging-accept-anyone-toggle', false)
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.authorizedSenders'),
                help: i18n.t('settings.messaging.editor.authorizedSendersHint'),
                fieldKey: 'authorized-senders',
                control: `<textarea id="${uiAttr(modalUiId(modalId, 'authorized-senders')).html}" class="setting-textarea setting-textarea--wide setting-input--full form-input" rows="4" placeholder="${uiAttr(i18n.t('settings.messaging.editor.authorizedSendersPlaceholder')).html}"></textarea>`
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.plaintextSecrets'),
                help: i18n.t('settings.messaging.editor.plaintextSecretsWarning'),
                fieldKey: 'plaintext-secrets',
                control: renderToggle(modalId, 'plaintext-secrets', 'messaging-plaintext-secret-toggle', false)
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.replaceCallback'),
                help: i18n.t('settings.messaging.editor.replaceCallbackWarning'),
                fieldKey: 'replace-callback',
                attributes: { id: modalUiId(modalId, 'replace-callback-item') },
                control: renderToggle(modalId, 'replace-callback', 'messaging-replace-callback-toggle', false)
            })
        ])
    });

const renderExecutionGroup = (modalId: string): string => {
    const modes = `<option value="chat">${uiText(i18n.t('chat.agent.mode.chat')).html}</option><option value="plan">${uiText(i18n.t('chat.agent.mode.plan')).html}</option><option value="execute">${uiText(i18n.t('chat.agent.mode.execute')).html}</option>`;
    const workspace = buildWorkspaceFolderFieldMarkup({
        pathInputId: modalUiId(modalId, 'workspace'),
        changeButtonId: modalUiId(modalId, 'workspace-change'),
        label: i18n.t('chat.configuration.filesFolder.currentLabel'),
        buttonLabel: i18n.t('chat.configuration.filesFolder.changeButton'),
        action: MESSAGING_MODAL_ACTION_WORKSPACE,
        status: false
    }).html;
    return renderSettingsSubgroup({
        title: i18n.t('settings.messaging.editor.executionTitle'),
        description: i18n.t('settings.messaging.editor.executionDescription'),
        tagName: 'section',
        className: 'messaging-account-modal__group messaging-account-modal__shared-controls',
        content: renderSettingsGroup([
            renderSettingItem({
                label: renderRequiredFieldLabelHtml(i18n.t('settings.messaging.editor.model')),
                fieldKey: 'model',
                control: renderSelect(modalUiId(modalId, 'model'), '')
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.agentMode'),
                fieldKey: 'agent-mode',
                control: renderSelect(modalUiId(modalId, 'agent-mode'), modes)
            }),
            workspace,
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.userName'),
                fieldKey: 'user-name',
                control: renderInput(modalUiId(modalId, 'user-name'))
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.assistantName'),
                fieldKey: 'assistant-name',
                control: renderInput(modalUiId(modalId, 'assistant-name'))
            }),
            renderSettingItem({
                label: i18n.t('settings.messaging.editor.parameters.fieldLabel'),
                help: i18n.t('settings.messaging.editor.parameters.description'),
                fieldKey: 'parameters',
                className: 'messaging-account-modal__parameters',
                control: `<div class="form-row-split form-row-split--with-action messaging-account-modal__parameters-row"><div class="form-col-main"><input id="${uiAttr(modalUiId(modalId, 'parameters-summary')).html}" class="setting-input setting-input--wide setting-input--full form-input" type="text" readonly></div><div class="form-col-action"><button type="button" id="${uiAttr(modalUiId(modalId, 'parameters-button')).html}" class="ui-button" data-action="${uiAttr(MESSAGING_MODAL_ACTION_PARAMETERS).html}" aria-label="${uiAttr(i18n.t('settings.messaging.editor.parameters.button')).html}" data-tooltip="${uiAttr(i18n.t('settings.messaging.editor.parameters.button')).html}">${uiText(i18n.t('settings.messaging.editor.parameters.button')).html}</button></div></div>`
            })
        ])
    });
};

const renderMcpGroup = (modalId: string): string =>
    renderSettingsSubgroup({
        title: i18n.t('settings.messaging.editor.toolsTitle'),
        description: i18n.t('settings.messaging.editor.toolsDescription'),
        tagName: 'section',
        className: 'messaging-account-modal__group messaging-account-modal__mcp setting-change-surface',
        content: buildMcpConversationSettingsBodyMarkup({
            modalId,
            includeServersList: false,
            toolsEnabledToggle: {
                label: uiText(i18n.t('chat.configuration.mcp.tools_enabled')).html,
                hint: uiText(i18n.t('chat.configuration.mcp.toolsEnabledHint')).html,
                action: MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE
            },
            toolApprovalRequiredToggle: {
                label: uiText(i18n.t('chat.configuration.mcp.tool_approval_required')).html,
                hint: uiText(i18n.t('chat.configuration.mcp.toolApprovalRequiredHint')).html,
                action: MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE
            },
            strings: {
                serversEmpty: uiText(i18n.t('chat.configuration.mcp.noServers')).html,
                toolsEmpty: uiText(i18n.t('chat.configuration.mcp.noTools')).html,
                enabledLabelAttr: uiAttr(i18n.t('common.enabled')).html,
                disabledLabelAttr: uiAttr(i18n.t('common.disabled')).html,
                disabledLabel: uiText(i18n.t('common.disabled')).html
            }
        })
    });

const createMessagingAccountModalElement = (modalId: string): HTMLElement => {
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('settings.messaging.modal.title'),
        description: i18n.t('settings.messaging.editor.description'),
        titleId: modalUiId(modalId, 'title')
    });
    const submitLabel = uiAttr(i18n.t('common.save')).html;
    const form = `<form id="${uiAttr(modalUiId(modalId, 'form')).html}" class="messaging-account-modal__form" novalidate>${renderIdentityGroup(modalId)}${renderCredentialGroup(modalId)}${renderAccessGroup(modalId)}${renderExecutionGroup(modalId)}${renderMcpGroup(modalId)}<button type="submit" aria-label="${submitLabel}" data-tooltip="${submitLabel}" hidden></button></form>`;
    const error = `<div id="${uiAttr(modalUiId(modalId, 'error')).html}" class="messaging-account-modal__error settings-card-surface" role="alert" aria-live="assertive" aria-atomic="true" hidden></div>`;
    const body = renderModalBody(toTrustedUiHtml(`${form}${error}`), { className: 'messaging-account-modal__body' });
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({
            modalId,
            id: modalUiId(modalId, 'cancel-btn'),
            text: i18n.t('common.cancel')
        }),
        right: renderModalFooterActionButton({
            text: i18n.t('common.save'),
            id: modalUiId(modalId, 'save-btn'),
            variant: 'accent',
            action: MESSAGING_MODAL_ACTION_SAVE,
            disabled: true
        })
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'settings' },
        contentClassName: 'messaging-account-modal__content chat-configuration-modal',
        header,
        body,
        footer
    });
};

const renderMessagingParametersModalMarkup = (): TrustedHtml =>
    renderChatParameterEditorModalMarkup({
        modalId: SETTINGS_MESSAGING_PARAMETERS_MODAL_ID,
        title: i18n.t('settings.messaging.editor.parameters.title'),
        description: i18n.t('settings.messaging.editor.parameters.description'),
        closeLabel: i18n.t('common.close'),
        cancelLabel: i18n.t('common.cancel'),
        saveLabel: i18n.t('common.save'),
        pageScope: 'settings',
        includeSystemPromptLock: false
    });

export const MESSAGING_MCP_ACTIONS = {
    serverToggle: MESSAGING_MODAL_ACTION_MCP_SERVER_TOGGLE,
    toolToggle: MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE,
    toolModeSelect: MESSAGING_MODAL_ACTION_MCP_MODE_SELECT,
    toolGroupToggle: MESSAGING_MODAL_ACTION_MCP_GROUP_TOGGLE,
    toolSearch: MESSAGING_MODAL_ACTION_MCP_SEARCH
};
export { createMessagingAccountModalElement, renderMessagingParametersModalMarkup };
