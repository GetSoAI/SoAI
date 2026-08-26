/* SoAI - Chat feature color toolkit [frontend/assets/ts/features/chat/ChatColorToolkit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { BaseColorToolkit, COLOR_GROUPS, type ColorKey, type ColorToolkitConfig, type ColorToolkitHost, type ColorValueInput } from '@core/ui/colorToolkitBase.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';

const CHAT_COLOR_CONFIG: ColorToolkitConfig = {
    cssPrefix: 'chat-color',
    pickerClassName: 'chat-conversation-color-picker',
    selectActionName: 'select-conversation-color',
    dataAttributeName: 'conversationColor',
    resolvePickerLabel: () => i18n.t('chat.colors.pickerLabel'),
    resolveOptionLabel: (key: ColorKey): string => {
        switch (key) {
            case 'none':
                return i18n.t('chat.colors.none');
            case 'red':
                return i18n.t('chat.colors.red');
            case 'yellow':
                return i18n.t('chat.colors.yellow');
            case 'purple':
                return i18n.t('chat.colors.purple');
            case 'green':
                return i18n.t('chat.colors.green');
            case 'blue':
                return i18n.t('chat.colors.blue');
            default: {
                const exhaustiveCheck: never = key;
                throw new Error(`Unhandled chat color label: ${String(exhaustiveCheck)}`);
            }
        }
    },
    errorMessage: 'Chat color toolkit requires host'
};

class ChatColorToolkit extends BaseColorToolkit {
    constructor(host: ColorToolkitHost) {
        super(host, CHAT_COLOR_CONFIG);
    }

    override renderPicker(selectedColor: ColorValueInput, isFavorite: boolean = false, exportDisabled: boolean = false): HTMLDivElement {
        const normalized = this.normalize(selectedColor);
        const documentRef = this.host.dom.getDocument();
        const picker = documentRef.createElement('div');
        picker.className = `${this.config.pickerClassName} soai-dropdown-menu`;
        picker.setAttribute('role', 'radiogroup');
        picker.setAttribute('aria-label', i18n.t('chat.colors.pickerLabel'));
        const colors = documentRef.createElement('div');
        colors.className = 'chat-color-picker-colors';
        picker.appendChild(colors);
        COLOR_GROUPS.forEach((option) => {
            const isSelected = option.value === null ? normalized === null : normalized === option.value;
            const button = documentRef.createElement('button');
            button.type = 'button';
            const classes = ['chat-color-option', `chat-color-option-${option.key}`];
            if (isSelected) {
                classes.push('is-selected');
            }
            button.className = classes.join(' ');
            button.dataset['action'] = 'select-conversation-color';
            const optionValue = option.value;
            button.dataset['color'] = isString(optionValue) ? optionValue : '';
            const label = this.getLabel(option.value);
            button.setAttribute('aria-label', label);
            setTooltipText(button, label);
            button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            colors.appendChild(button);
        });
        const actions = documentRef.createElement('div');
        actions.className = 'chat-color-picker-actions';
        picker.appendChild(actions);
        const renameBtn = documentRef.createElement('button');
        renameBtn.type = 'button';
        renameBtn.className = 'chat-color-option chat-color-option-rename';
        renameBtn.dataset['action'] = 'chat:start-conversation-rename';
        renameBtn.setAttribute('aria-label', i18n.t('common.edit'));
        setTooltipText(renameBtn, i18n.t('common.edit'));
        actions.appendChild(renameBtn);
        const archiveBtn = documentRef.createElement('button');
        archiveBtn.type = 'button';
        archiveBtn.className = 'chat-color-option chat-color-option-archive';
        archiveBtn.dataset['action'] = 'chat:archive-conversation';
        const archiveLabel = i18n.t('chat.conversation.archiveTitle');
        archiveBtn.setAttribute('aria-label', archiveLabel);
        setTooltipText(archiveBtn, archiveLabel);
        actions.appendChild(archiveBtn);
        const exportBtn = documentRef.createElement('button');
        exportBtn.type = 'button';
        exportBtn.className = 'chat-color-option chat-color-option-export';
        exportBtn.dataset['action'] = CHAT_ACTIONS.EXPORT_CONVERSATION_ITEM;
        exportBtn.disabled = exportDisabled;
        const exportLabel = i18n.t('chat.header.export');
        exportBtn.setAttribute('aria-label', exportLabel);
        setTooltipText(exportBtn, exportLabel);
        actions.appendChild(exportBtn);
        const favoriteBtn = documentRef.createElement('button');
        favoriteBtn.type = 'button';
        const favoriteClasses = ['chat-color-option', 'chat-color-option-favorite'];
        if (isFavorite) favoriteClasses.push('is-selected');
        favoriteBtn.className = favoriteClasses.join(' ');
        favoriteBtn.dataset['action'] = 'toggle-conversation-favorite';
        const favoriteLabel = isFavorite ? i18n.t('chat.colors.removeFavorite') : i18n.t('chat.colors.favorite');
        favoriteBtn.setAttribute('aria-label', favoriteLabel);
        setTooltipText(favoriteBtn, favoriteLabel);
        favoriteBtn.setAttribute('aria-pressed', isFavorite ? 'true' : 'false');
        actions.appendChild(favoriteBtn);
        return picker;
    }

    applyToConversationItem(item: HTMLElement | null | undefined, colorValue: ColorValueInput): void {
        if (!item) return;
        const normalized = this.normalize(colorValue);
        if (normalized) {
            item.dataset['conversationColor'] = normalized;
        } else {
            delete item.dataset['conversationColor'];
        }
    }
}

export { COLOR_GROUPS, ChatColorToolkit };
