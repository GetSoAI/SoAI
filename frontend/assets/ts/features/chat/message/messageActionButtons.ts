/* SoAI - Chat feature message action buttons [frontend/assets/ts/features/chat/message/messageActionButtons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { CHAT_ICON_SIZE_XS } from '@features/chat/chatConstants.ts';

interface MessageActionButtonRenderContext {
    escapeAttribute(value: string): string;
    getIcon(name: IconName, options?: IconOptions): string;
}

interface MessageActionButtonMarkupArguments {
    action: string;
    ariaLabel: string;
    className: string;
    iconHtml: string;
    title?: string;
    dataAttributes?: Record<string, string>;
}

interface MessageActionButtonDefinition {
    action: string;
    className: string;
    iconName: IconName;
    label: string;
    iconOptions?: IconOptions;
    dataAttributes?: Record<string, string>;
    extraIconHtml?: string;
    title?: string;
}

interface AssistantActionDefinitionArguments {
    infoTooltipText: string;
    copyLabel: string;
    infoLabel: string;
    speakLabel: string;
    stopSpeakingLabel: string;
    regenerateLabel: string;
    stopIconHtml: string;
}

interface CompactionBoundaryActionDefinitionArguments {
    regenerateLabel: string;
}

const renderMessageActionButton = (context: MessageActionButtonRenderContext, inputArguments: MessageActionButtonMarkupArguments): string => {
    const title = inputArguments.title ?? inputArguments.ariaLabel;
    const escapedAction = context.escapeAttribute(inputArguments.action);
    const escapedTitle = context.escapeAttribute(title);
    const escapedAriaLabel = context.escapeAttribute(inputArguments.ariaLabel);
    const dataAttributes = inputArguments.dataAttributes
        ? Object.entries(inputArguments.dataAttributes)
              .map(([key, value]) => ` ${key}="${context.escapeAttribute(value)}"`)
              .join('')
        : '';
    return `<button type="button" class="${inputArguments.className}" data-action="${escapedAction}"${dataAttributes} data-tooltip="${escapedTitle}" aria-label="${escapedAriaLabel}">${inputArguments.iconHtml}</button>`;
};

const renderMessageIcon = (context: MessageActionButtonRenderContext, name: IconName, options?: IconOptions): string => {
    const resolvedOptions = options ?? CHAT_ICON_SIZE_XS;
    const wrapperClassParts: string[] = ['ui-icon'];
    const extraClassName = resolvedOptions.className;
    if (isString(extraClassName) && extraClassName.trim()) {
        for (const part of extraClassName.trim().split(/\s+/)) {
            if (!part || part === 'ui-icon') {
                continue;
            }
            wrapperClassParts.push(part);
        }
    }
    const wrapperClassName = wrapperClassParts.join(' ');
    return renderIconSlot(context.getIcon(name, resolvedOptions), { className: wrapperClassName }).html;
};

const renderMessageActionButtons = (context: MessageActionButtonRenderContext, definitions: readonly MessageActionButtonDefinition[]): string => {
    const parts: string[] = [];
    for (const definition of definitions) {
        const iconHtml = renderMessageIcon(context, definition.iconName, definition.iconOptions) + (definition.extraIconHtml ?? '');
        const inputArguments: MessageActionButtonMarkupArguments = {
            action: definition.action,
            ariaLabel: definition.label,
            className: definition.className,
            iconHtml
        };
        if (definition.title !== undefined) {
            inputArguments.title = definition.title;
        }
        if (definition.dataAttributes !== undefined) {
            inputArguments.dataAttributes = definition.dataAttributes;
        }
        parts.push(renderMessageActionButton(context, inputArguments));
    }
    return parts.join('');
};

const resolveUserActionDefinitions = (): MessageActionButtonDefinition[] => {
    return [
        {
            action: 'copy',
            className: 'message-action ui-icon-button ui-icon-button-small copy-message-btn',
            iconName: 'copy',
            label: i18n.t('chat.message.actions.copy')
        },
        {
            action: 'edit',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-warning edit-message-btn',
            iconName: 'edit',
            label: i18n.t('common.edit')
        },
        {
            action: 'edit-save',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-accent edit-message-save-btn',
            iconName: 'check',
            label: i18n.t('common.save')
        },
        {
            action: 'edit-cancel',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-neutral edit-message-cancel-btn',
            iconName: 'close',
            label: i18n.t('common.cancel')
        }
    ];
};

const resolveAssistantActionDefinitions = (inputArguments: AssistantActionDefinitionArguments): MessageActionButtonDefinition[] => {
    return [
        {
            action: 'copy',
            className: 'message-action ui-icon-button ui-icon-button-small copy-message-btn',
            iconName: 'copy',
            label: inputArguments.copyLabel
        },
        {
            action: 'info',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-neutral info-message-btn',
            iconName: 'info',
            label: inputArguments.infoLabel,
            title: inputArguments.infoTooltipText
        },
        {
            action: 'speak',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-accent speak-message-btn',
            iconName: 'speaker',
            iconOptions: { className: 'ui-icon speak-message-btn-icon speak-message-btn-icon--speak' },
            extraIconHtml: inputArguments.stopIconHtml,
            label: inputArguments.speakLabel,
            dataAttributes: {
                'data-speak-label': inputArguments.speakLabel,
                'data-stop-label': inputArguments.stopSpeakingLabel
            }
        },
        {
            action: 'regenerate',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-neutral regenerate-message-btn',
            iconName: 'refresh',
            label: inputArguments.regenerateLabel
        }
    ];
};

const resolveCompactionBoundaryActionDefinitions = (inputArguments: CompactionBoundaryActionDefinitionArguments): MessageActionButtonDefinition[] => {
    return [
        {
            action: 'regenerate',
            className: 'message-action ui-icon-button ui-icon-button-small ui-variant-neutral regenerate-message-btn',
            iconName: 'refresh',
            label: inputArguments.regenerateLabel
        }
    ];
};

export { renderMessageActionButton, renderMessageActionButtons, renderMessageIcon, resolveAssistantActionDefinitions, resolveCompactionBoundaryActionDefinitions, resolveUserActionDefinitions };
export type { AssistantActionDefinitionArguments, CompactionBoundaryActionDefinitionArguments, MessageActionButtonDefinition, MessageActionButtonRenderContext };
