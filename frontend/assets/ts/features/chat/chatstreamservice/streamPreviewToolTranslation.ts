/* SoAI - Chat stream tool status preview translation [frontend/assets/ts/features/chat/chatstreamservice/streamPreviewToolTranslation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonRecord } from '@core/types/jsonValues.ts';

import { translateChatStreamAutomationToolPreviewKey } from '@features/chat/chatstreamservice/streamPreviewToolTranslationAutomation.ts';
import { translateChatStreamContentToolPreviewKey } from '@features/chat/chatstreamservice/streamPreviewToolTranslationContent.ts';
import { translateChatStreamIntegrationToolPreviewKey } from '@features/chat/chatstreamservice/streamPreviewToolTranslationIntegrations.ts';

const translateChatStreamToolPreviewKey = (previewKey: string, previewArguments: JsonRecord | null | undefined): string | null => {
    const normalizedPreviewArguments = previewArguments ?? undefined;
    const automationPreview = translateChatStreamAutomationToolPreviewKey(previewKey, normalizedPreviewArguments);
    if (automationPreview !== null) {
        return automationPreview;
    }
    const contentPreview = translateChatStreamContentToolPreviewKey(previewKey, normalizedPreviewArguments);
    if (contentPreview !== null) {
        return contentPreview;
    }
    return translateChatStreamIntegrationToolPreviewKey(previewKey, normalizedPreviewArguments);
};

export { translateChatStreamToolPreviewKey };
