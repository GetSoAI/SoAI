/* SoAI - Chat feature page markup context [frontend/assets/ts/features/chat/modals/markup/chatPageMarkupContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { requireSanitizer } from '@features/chat/chattemplates/sanitizer.ts';
import { resolveTemplateStrings } from '@features/chat/chattemplates/stringSet.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

interface ChatPageMarkupContext {
    strings: ChatTemplateStringSet;
    sanitizer: SanitizerApi;
    isDetached: boolean;
    sectionHeader: (label: string) => string;
    modelSectionHeader: (label: string) => string;
}

const createChatPageMarkupContext = (sanitizer: SanitizerApi, isDetached: boolean): ChatPageMarkupContext => {
    const resolvedSanitizer = requireSanitizer(sanitizer);
    const strings = resolveTemplateStrings(resolvedSanitizer);

    const settingsLinkButton = `<button type="button" class="ui-button chat-settings-link" data-action="chat:goto-settings-mcp" aria-label="${strings.settingsLinkTitle}" data-tooltip="${strings.settingsLinkTitle}">${strings.settingsLabel}</button>`;
    const modelSettingsLinkButton = `<button type="button" class="ui-button model-settings-link" data-action="chat:goto-model-settings" aria-label="${strings.settingsLinkTitle}" data-tooltip="${strings.settingsLinkTitle}">${strings.settingsLabel}</button>`;
    const sectionHeader = (label: string): string => `<div class="chat-configuration-section-header"><div class="chat-configuration-section-title">${label}</div>${settingsLinkButton}</div>`;
    const modelSectionHeader = (label: string): string => `<div class="chat-configuration-section-header"><div class="chat-configuration-section-title">${label}</div>${modelSettingsLinkButton}</div>`;

    return Object.freeze({
        strings,
        sanitizer: resolvedSanitizer,
        isDetached,
        sectionHeader,
        modelSectionHeader
    });
};

export { createChatPageMarkupContext };
export type { ChatPageMarkupContext };
