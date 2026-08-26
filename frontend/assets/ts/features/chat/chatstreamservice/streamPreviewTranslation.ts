/* SoAI - Chat feature stream preview translation [frontend/assets/ts/features/chat/chatstreamservice/streamPreviewTranslation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';
import { resolveContextCompactionStreamPreviewText } from '@features/chat/stream/contextCompactionStreamPreview.ts';
import { translateChatStreamToolPreviewKey } from '@features/chat/chatstreamservice/streamPreviewToolTranslation.ts';

const translateChatStreamPreviewKey = (previewKey: string, previewArguments: JsonRecord | null | undefined): string => {
    switch (previewKey) {
        case 'chat.stream.preview.phases.loading.1':
            return i18n.t('chat.stream.preview.phases.loading.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.loading.2':
            return i18n.t('chat.stream.preview.phases.loading.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.processing.1':
            return i18n.t('chat.stream.preview.phases.processing.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.processing.2':
            return i18n.t('chat.stream.preview.phases.processing.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.responding.1':
            return i18n.t('chat.stream.preview.phases.responding.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.responding.2':
            return i18n.t('chat.stream.preview.phases.responding.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.running_tool.1':
            return i18n.t('chat.stream.preview.phases.running_tool.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.running_tool.2':
            return i18n.t('chat.stream.preview.phases.running_tool.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.context_compaction.1':
            return resolveContextCompactionStreamPreviewText();
        case 'chat.stream.preview.phases.thinking.1':
            return i18n.t('chat.stream.preview.phases.thinking.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.thinking.2':
            return i18n.t('chat.stream.preview.phases.thinking.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.waiting_for_user.1':
            return i18n.t('chat.stream.preview.phases.waiting_for_user.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.waiting_for_user.2':
            return i18n.t('chat.stream.preview.phases.waiting_for_user.2', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.working.1':
            return i18n.t('chat.stream.preview.phases.working.1', previewArguments ?? undefined).trim();
        case 'chat.stream.preview.phases.working.2':
            return i18n.t('chat.stream.preview.phases.working.2', previewArguments ?? undefined).trim();
        default:
            const toolPreviewText = translateChatStreamToolPreviewKey(previewKey, previewArguments);
            if (toolPreviewText !== null) {
                return toolPreviewText;
            }
            throw new Error(`Unknown chat stream preview translation key: ${previewKey}`);
    }
};

export { translateChatStreamPreviewKey };
