/* SoAI - Chat feature agent mode labels [frontend/assets/ts/features/chat/agent/agentModeLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { i18n } from '@core/i18n/index.ts';

const resolveAgentModeLabel = (mode: AgentMode): string => {
    switch (mode) {
        case 'chat':
            return i18n.t('chat.agent.mode.chat');
        case 'plan':
            return i18n.t('chat.agent.mode.plan');
        case 'execute':
            return i18n.t('chat.agent.mode.execute');
        default: {
            const exhaustiveCheck: never = mode;
            throw new Error(`Unhandled agent mode label: ${String(exhaustiveCheck)}`);
        }
    }
};

export { resolveAgentModeLabel };
