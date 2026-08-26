/* SoAI - Chat page model availability controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/ChatPageModelAvailabilityController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasChatSelectableModels, isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

type ChatPageModelAvailabilityHost = {
    getModelIndex(): Map<string, ModelData>;
    getModels(): readonly ModelData[];
    getModelStreamHasPayload(): boolean;
};

class ChatPageModelAvailabilityController {
    readonly #host: ChatPageModelAvailabilityHost;

    constructor(host: ChatPageModelAvailabilityHost) {
        this.#host = host;
    }

    getModelStreamHasPayload = (): boolean => {
        return this.#host.getModelStreamHasPayload();
    };

    hasSelectableModels = (): boolean => {
        return hasChatSelectableModels(this.#host.getModels());
    };

    isModelAvailable = (modelId: string): boolean => {
        const normalized = modelId.trim();
        if (!normalized) {
            return false;
        }
        const model = this.#host.getModelIndex().get(normalized) ?? null;
        return model !== null && isChatSelectableModel(model);
    };
}

export { ChatPageModelAvailabilityController };
