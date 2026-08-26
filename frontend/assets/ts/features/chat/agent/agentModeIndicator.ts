/* SoAI - Chat feature agent mode indicator [frontend/assets/ts/features/chat/agent/agentModeIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';

const applyAgentModeBorderIndicator = (chatInput: HTMLTextAreaElement, mode: AgentMode): void => {
    if (mode === 'chat') {
        chatInput.removeAttribute('data-agent-mode');
        return;
    }
    chatInput.setAttribute('data-agent-mode', mode);
};

export { applyAgentModeBorderIndicator };
