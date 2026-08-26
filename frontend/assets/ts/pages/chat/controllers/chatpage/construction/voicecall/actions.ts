/* SoAI - Chat page voice call toggle action [frontend/assets/ts/pages/chat/controllers/chatpage/construction/voicecall/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

export type VoiceCallActionId = 'toggleCall';

interface VoiceCallToggleHost extends ChatVoiceSessionHost {
    runUiTask(operationId: string, task: () => Promise<void> | void): void;
}

const isVoiceCallActionId = (value: string): value is VoiceCallActionId => value === 'toggleCall';

const handleVoiceCallToggleForPage = (host: VoiceCallToggleHost): void => {
    host.voiceSession.toggleCall((task) => host.runUiTask('chat:toggleCall', task));
};

export { handleVoiceCallToggleForPage, isVoiceCallActionId };
