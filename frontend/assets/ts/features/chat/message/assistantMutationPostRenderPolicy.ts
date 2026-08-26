/* SoAI - Assistant message mutation post-render request policy [frontend/assets/ts/features/chat/message/assistantMutationPostRenderPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPostRenderRequestType } from '@features/chat/message/types.ts';

type AssistantMutationPostRenderSurface = 'agentPatch' | 'comparisonSlide' | 'currentConversationRefresh' | 'terminalFinalize';

type AssistantMutationPostRenderArguments = {
    changed: boolean;
    requiresPostRender: boolean;
    surface: AssistantMutationPostRenderSurface;
};

const resolveAssistantMutationPostRenderType = (inputArguments: AssistantMutationPostRenderArguments): ChatPostRenderRequestType | null => {
    if (inputArguments.surface === 'terminalFinalize') {
        return 'terminal';
    }
    if (inputArguments.surface === 'agentPatch') {
        return inputArguments.changed || inputArguments.requiresPostRender ? 'full' : null;
    }
    return inputArguments.requiresPostRender ? 'canonicalFull' : null;
};

export { resolveAssistantMutationPostRenderType };
export type { AssistantMutationPostRenderSurface };
