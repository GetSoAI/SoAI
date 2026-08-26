/* SoAI - Chat feature memory profile modal markup [frontend/assets/ts/features/chat/modals/markup/chatMemoryProfileModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { CHAT_MEMORY_PROFILE_MODAL_ID } from '@features/chat/modals/constants.ts';
import { CHAT_MEMORY_PROFILE_FIELD_NAMES, type ChatMemoryProfileFieldDefinition, type ChatMemoryProfileFieldName, resolveChatMemoryProfileFieldDefinition } from '@features/chat/modals/chatMemoryProfileFields.ts';

const translateChatMemoryProfileFieldLabel = (fieldName: ChatMemoryProfileFieldName): string => {
    switch (fieldName) {
        case 'preferred_name':
            return i18n.t('chat.memory.profile.fields.preferred_name.label');
        case 'assistant_name':
            return i18n.t('chat.memory.profile.fields.assistant_name.label');
        case 'role_background':
            return i18n.t('chat.memory.profile.fields.role_background.label');
        case 'current_goals':
            return i18n.t('chat.memory.profile.fields.current_goals.label');
        case 'preferences':
            return i18n.t('chat.memory.profile.fields.preferences.label');
        case 'dislikes_to_avoid':
            return i18n.t('chat.memory.profile.fields.dislikes_to_avoid.label');
        case 'communication_style':
            return i18n.t('chat.memory.profile.fields.communication_style.label');
        case 'recurring_tools_projects':
            return i18n.t('chat.memory.profile.fields.recurring_tools_projects.label');
        case 'extra_notes':
            return i18n.t('chat.memory.profile.fields.extra_notes.label');
    }
};

const translateChatMemoryProfileFieldPlaceholder = (fieldName: ChatMemoryProfileFieldName): string => {
    switch (fieldName) {
        case 'preferred_name':
            return i18n.t('chat.memory.profile.fields.preferred_name.placeholder');
        case 'assistant_name':
            return i18n.t('chat.memory.profile.fields.assistant_name.placeholder');
        case 'role_background':
            return i18n.t('chat.memory.profile.fields.role_background.placeholder');
        case 'current_goals':
            return i18n.t('chat.memory.profile.fields.current_goals.placeholder');
        case 'preferences':
            return i18n.t('chat.memory.profile.fields.preferences.placeholder');
        case 'dislikes_to_avoid':
            return i18n.t('chat.memory.profile.fields.dislikes_to_avoid.placeholder');
        case 'communication_style':
            return i18n.t('chat.memory.profile.fields.communication_style.placeholder');
        case 'recurring_tools_projects':
            return i18n.t('chat.memory.profile.fields.recurring_tools_projects.placeholder');
        case 'extra_notes':
            return i18n.t('chat.memory.profile.fields.extra_notes.placeholder');
    }
};

const buildFieldMarkup = (fieldName: ChatMemoryProfileFieldName): string => {
    const modalId = CHAT_MEMORY_PROFILE_MODAL_ID;
    const definition = resolveChatMemoryProfileFieldDefinition(fieldName);
    const label = translateChatMemoryProfileFieldLabel(fieldName);
    const placeholder = translateChatMemoryProfileFieldPlaceholder(fieldName);
    if (definition.inputType === 'text') {
        return buildTextFieldMarkup(definition, label, placeholder, modalId);
    }
    return buildTextareaFieldMarkup(definition, label, placeholder, modalId);
};

const buildTextFieldMarkup = (definition: ChatMemoryProfileFieldDefinition, label: string, placeholder: string, modalId: string): string => {
    const fieldIdText = modalUiId(modalId, definition.uiToken);
    const fieldId = uiAttr(fieldIdText);
    const maxLength = definition.maxLength ?? 50;
    return `<div class="form-group"><label for="${fieldId}">${label}</label><input type="text" id="${fieldId}" class="form-input chat-memory-profile-input" data-field="${uiAttr(definition.name)}" maxlength="${uiAttr(String(maxLength))}" placeholder="${uiAttr(placeholder)}"></div>`;
};

const buildTextareaFieldMarkup = (definition: ChatMemoryProfileFieldDefinition, label: string, placeholder: string, modalId: string): string => {
    const fieldIdText = modalUiId(modalId, definition.uiToken);
    const fieldId = uiAttr(fieldIdText);
    const rows = definition.rows ?? 3;
    return `<div class="form-group"><label for="${fieldId}">${label}</label><textarea id="${fieldId}" class="form-input chat-memory-profile-input" data-field="${uiAttr(definition.name)}" rows="${uiAttr(String(rows))}" placeholder="${uiAttr(placeholder)}"></textarea></div>`;
};

const createChatMemoryProfileModalElement = (): HTMLElement => {
    const modalId = CHAT_MEMORY_PROFILE_MODAL_ID;
    const fieldsMarkup = toTrustedUiHtml(CHAT_MEMORY_PROFILE_FIELD_NAMES.map((fieldName) => buildFieldMarkup(fieldName)).join(''));
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('chat.memory.profile.title'),
        description: i18n.t('common.modalDescriptions.chatMemoryProfile'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(uiHtml`
        <div class="chat-memory-profile-copy">${i18n.t('chat.memory.profile.description')}</div>
        <div class="chat-memory-profile-grid">${fieldsMarkup}</div>
    `);
    const skipText = i18n.t('chat.memory.profile.skip');
    const saveText = i18n.t('chat.memory.profile.save');
    const footer = renderSplitModalFooter({
        left: renderModalFooterActionButton({ id: modalUiId(modalId, 'skip'), text: skipText, variant: 'neutral' }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save'), text: saveText, variant: 'accent' })
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'chat' },
        header,
        body,
        footer
    });
};

export { createChatMemoryProfileModalElement };
