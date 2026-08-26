/* SoAI - Chat feature render host [frontend/assets/ts/features/chat/message/messageview/renderHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import { i18n } from '@core/i18n/index.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { RichTextRenderer } from '@core/richtextrenderer/service.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

type MainThreadChatMessageRenderHostDependencies = {
    sanitizer: SanitizerApi;
    getCanonicalPlan: () => AgentCanonicalPlan | null;
    getIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    getToolIconHtml: (toolName: string) => string | null;
    isRichTextEnabled: () => boolean;
    isCodeRecognitionEnabled: () => boolean;
    isInlineMultimediaPreviewsEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    isCurrentConversationExecuting: () => boolean;
};

const createMainThreadChatMessageRenderHost = (dependencies: MainThreadChatMessageRenderHostDependencies): ChatMessageRenderHost => {
    const richTextRenderer = new RichTextRenderer({
        sanitizer: dependencies.sanitizer,
        translateFootnoteBackRef: () => i18n.t('richText.footnotes.backToReference'),
        isCodeRecognitionEnabled: () => dependencies.isCodeRecognitionEnabled()
    });

    return {
        nowMs: serverEpochMs,
        getCanonicalPlan: () => dependencies.getCanonicalPlan(),
        escapeHtml: (unsafe: string) => dependencies.sanitizer.html(unsafe),
        escapeAttribute: (value: string) => dependencies.sanitizer.attribute(value),
        sanitizeImage: (value: string) => dependencies.sanitizer.image(value),
        getIconHtml: (name: IconName, options?: IconOptions) => dependencies.getIcon(name, options).html,
        getToolIconHtml: (toolName: string) => dependencies.getToolIconHtml(toolName),
        isRichTextEnabled: () => dependencies.isRichTextEnabled(),
        isInlineMultimediaPreviewsEnabled: () => dependencies.isInlineMultimediaPreviewsEnabled(),
        isShowActivitiesEnabled: () => dependencies.isShowActivitiesEnabled(),
        getActivityDurationDisplayMode: () => dependencies.getActivityDurationDisplayMode(),
        isCurrentConversationExecuting: () => dependencies.isCurrentConversationExecuting(),
        renderRichText: (content, wrapCodeBlock, options = {}) => {
            return richTextRenderer.render(content, { ...options, wrapCodeBlock });
        }
    };
};

export { createMainThreadChatMessageRenderHost };
export type { MainThreadChatMessageRenderHostDependencies };
