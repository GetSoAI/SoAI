/* SoAI - Chat page model vision support controller [frontend/assets/ts/pages/chat/controllers/page/guards/modelVisionSupportController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { supportsVisionInputForModel } from '@core/openai/capabilityChecks.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';

type VisionSupportHost = ChatConversationStateHost;

const resolveVisionSupportForCurrentModel = (host: VisionSupportHost): boolean => {
    const currentModel = host.conversationState.currentModel;
    if (!isString(currentModel) || !currentModel.trim()) {
        return false;
    }
    const model = host.conversationState.modelIndex.get(currentModel.trim());
    return supportsVisionInputForModel(model ?? null);
};

export { resolveVisionSupportForCurrentModel };
export type { VisionSupportHost };
