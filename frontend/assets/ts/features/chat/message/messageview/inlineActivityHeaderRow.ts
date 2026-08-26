/* SoAI - Chat feature inline activity header row [frontend/assets/ts/features/chat/message/messageview/inlineActivityHeaderRow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { stripTrailingPreviewDot } from '@features/chat/message/messageview/inlineActivityText.ts';

type InlineActivityHeaderTagName = 'div' | 'span';
type InlineActivityLeadingVariant = 'expander' | 'hourglass' | 'dot';

const INLINE_ACTIVITY_CLOSE_BUTTON_CLASS = 'ui-round-button ui-round-button--inline inline-activity-close-button';
const INLINE_ACTIVITY_STOP_BUTTON_CLASS = 'ui-round-button ui-round-button--inline inline-activity-stop-button';

interface InlineActivityHeaderDependencies {
    escapeAttribute: (value: string) => string;
    escapeHtml: (value: string) => string;
    getIconHtml: (name: IconName, options?: IconOptions) => string;
}

interface InlineActivityPreviewArguments {
    text: string;
    rootAttributes?: string | undefined;
    rootClassName?: string | undefined;
    textAttributes?: string | undefined;
    hidden?: boolean | undefined;
}

interface InlineActivityStopButtonArguments {
    actionId: string;
    callId: string;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    label: string;
}

const renderInlineActivityLeadingIcon = (
    dependencies: InlineActivityHeaderDependencies,
    inputArguments: {
        variant: InlineActivityLeadingVariant;
        iconName: IconName;
        options: IconOptions;
        overlayText?: string | undefined;
        overlayAttributes?: string | undefined;
    }
): string => {
    const icon = dependencies.getIconHtml(inputArguments.iconName, inputArguments.options);
    const overlayText = inputArguments.overlayText ? inputArguments.overlayText.trim() : '';
    const overlayAttributes = inputArguments.overlayAttributes ? ` ${inputArguments.overlayAttributes.trim()}` : '';
    const overlayHtml = overlayText ? `<span class="inline-activity-leading-index"${overlayAttributes}>${dependencies.escapeHtml(overlayText)}</span>` : '';
    return `<span class="inline-activity-leading-icon" data-leading-variant="${dependencies.escapeAttribute(inputArguments.variant)}" aria-hidden="true">${overlayHtml}${icon}</span>`;
};

const renderInlineActivityIcon = (inputArguments: { innerHtml: string }): string => {
    return `<span class="inline-activity-icon" aria-hidden="true">${inputArguments.innerHtml}</span>`;
};

const renderInlineActivitySeparatorDot = (dependencies: InlineActivityHeaderDependencies, inputArguments?: { hidden?: boolean | undefined }): string => {
    const hiddenAttribute = inputArguments?.hidden ? ' hidden' : '';
    const icon = dependencies.getIconHtml('dot', { size: 10, strokeWidth: 1.5 });
    return `<span class="inline-activity-separator-dot" data-inline-activity-separator="true"${hiddenAttribute} aria-hidden="true">${icon}</span>`;
};

const renderInlineActivityPreview = (dependencies: InlineActivityHeaderDependencies, inputArguments: InlineActivityPreviewArguments): string => {
    const hiddenAttribute = inputArguments.hidden ? ' hidden' : '';
    const rootAttributes = inputArguments.rootAttributes ? ` ${inputArguments.rootAttributes.trim()}` : '';
    const rootClassName = inputArguments.rootClassName ? ` ${inputArguments.rootClassName.trim()}` : '';
    const textAttributes = inputArguments.textAttributes ? ` ${inputArguments.textAttributes.trim()}` : '';
    const previewText = stripTrailingPreviewDot(inputArguments.text);
    return `<span class="inline-activity-preview${rootClassName}"${hiddenAttribute}${rootAttributes}><span class="inline-activity-preview-text"${textAttributes}>${dependencies.escapeHtml(previewText)}</span></span>`;
};

const renderInlineActivityStopButton = (dependencies: InlineActivityHeaderDependencies, inputArguments: InlineActivityStopButtonArguments | null): string => {
    if (inputArguments === null) {
        return '';
    }
    const icon = dependencies.getIconHtml('stop', { size: 14, strokeWidth: 1.5 });
    const className = dependencies.escapeAttribute(INLINE_ACTIVITY_STOP_BUTTON_CLASS);
    const actionAttr = dependencies.escapeAttribute(inputArguments.actionId);
    const callIdAttr = dependencies.escapeAttribute(inputArguments.callId);
    const assistantTurnAttr = dependencies.escapeAttribute(String(inputArguments.assistantTurnAtMs));
    const modelVariantAttr = dependencies.escapeAttribute(String(inputArguments.modelVariantIndex));
    const labelAttr = dependencies.escapeAttribute(inputArguments.label);
    return `<button type="button" class="${className}" data-action="${actionAttr}" data-call-id="${callIdAttr}" data-assistant-turn-ts="${assistantTurnAttr}" data-model-variant-index="${modelVariantAttr}" aria-label="${labelAttr}" data-tooltip="${labelAttr}">${icon}</button>`;
};

const renderInlineActivityHeaderRow = (
    dependencies: InlineActivityHeaderDependencies,
    inputArguments: {
        tagName: InlineActivityHeaderTagName;
        leadingIconHtml: string;
        statusLedHtml: string;
        mainIconHtml: string;
        name: string;
        previewHtml: string;
        durationHtml: string;
        actionId?: string | undefined;
        callId?: string | undefined;
        requiresCallId?: boolean | undefined;
        toggleEnabled: boolean;
        separatorDotHidden?: boolean | undefined;
        expandedCloseButton?: boolean | undefined;
        stopButton?: InlineActivityStopButtonArguments | null | undefined;
    }
): string => {
    const attrs = (() => {
        if (!inputArguments.toggleEnabled) {
            return ` aria-disabled="true" data-toggle-disabled="true"`;
        }
        if (inputArguments.actionId && inputArguments.requiresCallId !== false && (!inputArguments.callId || !inputArguments.callId.trim())) {
            throw new Error('Inline activity toggle requires a call id.');
        }
        const action = inputArguments.actionId ? ` data-action="${dependencies.escapeAttribute(inputArguments.actionId)}"` : '';
        const callId = inputArguments.callId ? ` data-call-id="${dependencies.escapeAttribute(inputArguments.callId)}"` : '';
        return `${action}${callId} aria-disabled="false"`;
    })();

    const preview = inputArguments.previewHtml.trim();
    const duration = inputArguments.durationHtml.trim();
    const separatorDot = preview ? renderInlineActivitySeparatorDot(dependencies, { hidden: inputArguments.separatorDotHidden }) : '';
    const stopButton = renderInlineActivityStopButton(dependencies, inputArguments.stopButton ?? null);
    const closeButton = (() => {
        if (!inputArguments.expandedCloseButton || !inputArguments.actionId || !inputArguments.callId || !inputArguments.callId.trim()) {
            return '';
        }
        const label = i18n.t('common.close');
        const icon = dependencies.getIconHtml('close', { size: 14, strokeWidth: 1.5 });
        return `<button type="button" class="${dependencies.escapeAttribute(INLINE_ACTIVITY_CLOSE_BUTTON_CLASS)}" data-action="${dependencies.escapeAttribute(inputArguments.actionId)}" data-call-id="${dependencies.escapeAttribute(inputArguments.callId)}" aria-label="${dependencies.escapeAttribute(label)}" data-tooltip="${dependencies.escapeAttribute(label)}">${icon}</button>`;
    })();

    const rawName = inputArguments.name.trim();
    const escapedName = rawName ? dependencies.escapeAttribute(rawName) : '';
    const titleAttr = escapedName ? ` data-tooltip="${escapedName}"` : '';
    const ariaLabelAttr = escapedName ? ` aria-label="${escapedName}"` : '';
    const headerOpen = `<${inputArguments.tagName} class="inline-activity-header"${attrs}${titleAttr}${ariaLabelAttr}>`;
    const headerClose = `</${inputArguments.tagName}>`;
    return `${headerOpen}${inputArguments.leadingIconHtml}${inputArguments.statusLedHtml}${inputArguments.mainIconHtml}<span class="inline-activity-name">${dependencies.escapeHtml(inputArguments.name)}</span>${separatorDot}${preview}${duration}${stopButton}${closeButton}${headerClose}`;
};

export { renderInlineActivityHeaderRow, renderInlineActivityIcon, renderInlineActivityLeadingIcon, renderInlineActivityPreview };
export type { InlineActivityHeaderDependencies, InlineActivityLeadingVariant, InlineActivityStopButtonArguments };
