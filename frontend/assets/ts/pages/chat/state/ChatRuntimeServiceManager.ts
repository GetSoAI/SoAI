/* SoAI - Chat injected runtime service ownership [frontend/assets/ts/pages/chat/state/ChatRuntimeServiceManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireSyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import type { VoiceCallRuntimeAssets } from '@core/media/voiceCallRuntimeAssets.ts';
import type { ChatToolIconServiceContract } from '@core/chat/protocols.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { ChatConversationAttentionService, ChatPagePresenceService, ChatStreamService } from '@features/chat/public.ts';
import type { TimerHost } from '@pages/chat/controllers/chatUiBehaviors.ts';

interface ChatPageDependencies {
    chatStreamService: ChatStreamService;
    chatPagePresence: ChatPagePresenceService;
    chatConversationAttention: ChatConversationAttentionService;
    chatToolIconService: ChatToolIconServiceContract;
    firstRunModals: FirstRunModalService;
    voiceCallRuntimeAssets: VoiceCallRuntimeAssets;
}

class ChatRuntimeServices {
    readonly chatStream: ChatStreamService;
    readonly presence: ChatPagePresenceService;
    readonly attention: ChatConversationAttentionService;
    readonly toolIcons: ChatToolIconServiceContract;
    readonly firstRunModals: FirstRunModalService;
    readonly voiceCallAssets: VoiceCallRuntimeAssets;
    readonly syntaxHighlighter = requireSyntaxHighlighter();
    readonly timers: TimerHost;

    constructor(dependencies: ChatPageDependencies, timers: TimerHost) {
        this.chatStream = dependencies.chatStreamService;
        this.presence = dependencies.chatPagePresence;
        this.attention = dependencies.chatConversationAttention;
        this.toolIcons = dependencies.chatToolIconService;
        this.firstRunModals = dependencies.firstRunModals;
        this.voiceCallAssets = dependencies.voiceCallRuntimeAssets;
        this.timers = timers;
    }
}

export { ChatRuntimeServices };
export type { ChatPageDependencies };
export interface ChatRuntimeServicesHost {
    runtimeServices: ChatRuntimeServices;
}
