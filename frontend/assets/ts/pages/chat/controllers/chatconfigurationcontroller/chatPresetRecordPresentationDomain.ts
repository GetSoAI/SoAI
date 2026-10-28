/* SoAI - Preset record cards and shared preset action controls [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetRecordPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { CHAT_ACTIONS, CHAT_PRESET_SECTION_DEFINITIONS, translateChatPresetSection } from '@features/chat/public.ts';
import type { WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatPresetLibraryViewState } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';

type PresetRowActionPresentation = Readonly<{ className: string; icon: IconName; strokeWidth: number }>;

const presetRowActionPresentation = (action: string): PresetRowActionPresentation | null => {
    if (action === CHAT_ACTIONS.REMOVE_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--delete', icon: 'close', strokeWidth: 1.5 };
    if (action === CHAT_ACTIONS.REPLACE_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--settings', icon: 'replace', strokeWidth: 1.5 };
    if (action === CHAT_ACTIONS.RENAME_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--edit', icon: 'rename', strokeWidth: 1 };
    if (action === CHAT_ACTIONS.APPLY_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--success chat-preset-apply-action', icon: 'play', strokeWidth: 1.5 };
    return null;
};

const createPresetActionButton = (documentValue: Document, action: string, label: string, presetId: string | null, disabled: boolean): HTMLButtonElement => {
    const button = documentValue.createElement('button');
    button.type = 'button';
    const rowPresentation = presetRowActionPresentation(action);
    button.className = rowPresentation ? rowPresentation.className : action === CHAT_ACTIONS.SUBMIT_PRESET_EDITOR ? 'ui-button ui-variant-accent' : action === CHAT_ACTIONS.CANCEL_PRESET_EDITOR ? 'ui-button ui-variant-neutral' : 'ui-button ui-button--sm';
    button.dataset['action'] = action;
    if (presetId) button.dataset['presetId'] = presetId;
    button.disabled = disabled;
    button.dataset['presetBaseDisabled'] = disabled ? 'true' : 'false';
    button.setAttribute('aria-label', label);
    button.dataset['tooltip'] = label;
    if (rowPresentation) button.append(createIconSlot(documentValue, getIconSync(rowPresentation.icon, { strokeWidth: rowPresentation.strokeWidth })));
    else button.textContent = label;
    return button;
};

const renderBadges = (record: WebuiChatPresetRecord, container: HTMLElement): void => {
    for (const definition of CHAT_PRESET_SECTION_DEFINITIONS) {
        if (!(definition.id in record.sections)) continue;
        const badge = container.ownerDocument.createElement('span');
        badge.className = 'settings-record-badge';
        badge.textContent = translateChatPresetSection(definition.id);
        container.append(badge);
    }
};

const createPresetRow = (record: WebuiChatPresetRecord, state: ChatPresetLibraryViewState, documentValue: Document): HTMLElement => {
    const row = documentValue.createElement('article');
    row.className = 'collection-list-item chat-preset-row glass-surface-interactive';
    row.setAttribute('role', 'listitem');
    if (!record.applicable) row.classList.add('is-unavailable');
    row.dataset['presetId'] = record.id;
    const info = documentValue.createElement('div');
    info.className = 'collection-list-item-main';
    const title = documentValue.createElement('h3');
    title.className = 'collection-list-item-title';
    title.textContent = record.name;
    const meta = documentValue.createElement('div');
    meta.className = 'collection-list-item-meta';
    meta.textContent = i18n.t('chat.configuration.presetLibrary.modifiedAt', { value: formatDateTime(record.modifiedAtMs, false) });
    const badges = documentValue.createElement('div');
    badges.className = 'chat-preset-badges';
    renderBadges(record, badges);
    info.append(title, meta, badges);
    if (record.omittedSettingsCount > 0) {
        const warning = documentValue.createElement('div');
        warning.className = 'chat-configuration-hint is-warning';
        warning.textContent = i18n.t('chat.configuration.presetLibrary.omittedSettings', { count: record.omittedSettingsCount });
        info.append(warning);
    }
    if (!record.applicable) {
        const unavailable = documentValue.createElement('div');
        unavailable.className = 'chat-configuration-hint';
        unavailable.textContent = i18n.t('chat.configuration.presetLibrary.notApplicable');
        info.append(unavailable);
    }
    const actions = documentValue.createElement('div');
    actions.className = 'ui-collection-list__actions chat-preset-row-actions';
    const revisionsBlocked = state.stale;
    actions.append(createPresetActionButton(documentValue, CHAT_ACTIONS.REMOVE_PRESET, i18n.t('common.delete'), record.id, revisionsBlocked), createPresetActionButton(documentValue, CHAT_ACTIONS.REPLACE_PRESET, i18n.t('chat.configuration.presetLibrary.replaceAction'), record.id, revisionsBlocked), createPresetActionButton(documentValue, CHAT_ACTIONS.APPLY_PRESET, i18n.t('chat.configuration.presetLibrary.applyAction'), record.id, revisionsBlocked || !record.applicable), createPresetActionButton(documentValue, CHAT_ACTIONS.RENAME_PRESET, i18n.t('chat.configuration.presetLibrary.renameAction'), record.id, revisionsBlocked));
    row.append(info, actions);
    return row;
};

export { createPresetActionButton, createPresetRow };
