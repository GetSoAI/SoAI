/* SoAI - Staged configuration model control composition [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelControlComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import type { ConfigurationControllerStateAccess, ConfigurationModelControlHost } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';
import type { ConfigurationModelSelectionStateManager } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelSelectionStateManager.ts';
import { ChatModelControlController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts';
import { CHAT_MODEL_CONTROL_ROOT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';

const createConfigurationModelControl = (inputArguments: { host: ConfigurationModelControlHost; root: Element; state: ConfigurationControllerStateAccess; model: ConfigurationModelSelectionStateManager; onStateChange(): void }): ChatModelControlController => {
    const { host, state, model } = inputArguments;
    return new ChatModelControlController({
        pageDom: host.pageDom,
        pageContext: host.pageContext,
        getCachedIcon: (name, iconOptions) => host.getCachedIcon(name, iconOptions),
        get models() {
            return [...state.getModels()];
        },
        get modelIndex() {
            return new Map(state.getModelIndex());
        },
        get modelStreamHasPayload() {
            return state.hasModelCatalog();
        },
        hasSelectableModels: () => [...state.getModels()].some((candidate) => isChatSelectableModel(candidate)),
        getCurrentConversation: () => host.getCurrentConversation(),
        navigateWithQuery: (page, query) => host.navigateWithQuery(page, query),
        isConversationExecuting: (conversationId) => host.isConversationExecuting(conversationId),
        isModelSelectionLocked: () => host.isSelectionLocked(),
        resolveChatModelControlRoots: () => dom.resolveAll(CHAT_MODEL_CONTROL_ROOT_SELECTOR, inputArguments.root).filter((candidate): candidate is HTMLElement => candidate instanceof HTMLElement),
        resolveModelControlOverlayBoundary: () => {
            const boundary = dom.resolve('.modal-body', inputArguments.root);
            return boundary instanceof HTMLElement ? boundary : inputArguments.root instanceof HTMLElement ? inputArguments.root : null;
        },
        resolveEffectiveModels: () => model.workingModels(),
        applyEffectiveModels: async (models) => {
            model.stage(models);
        },
        updateModelUI: () => inputArguments.onStateChange()
    });
};

export { createConfigurationModelControl };
