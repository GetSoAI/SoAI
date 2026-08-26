/* SoAI - WebUI Chat interaction endpoints [frontend/assets/ts/core/api/endpoints/webuiChatInteractionEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeInteractionFocus, decodeInteractionResolution, decodePendingInteraction, type AskUserInteractionResolutionRequest, type ConversationAttentionRenderedRequest, type ConversationInteractionFocusResponse, type ConversationInteractionResolutionResponse, type ConversationPendingInteractionResponse, type SecretPromptInteractionResolutionRequest, type ToolApprovalInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { serializeAskUserInteractionResolution, serializeConversationAttentionRendered, serializeSecretPromptInteractionResolution, serializeToolApprovalInteractionResolution } from '@core/api/contracts/webuiInteractionSerialization.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { WebuiConversationInteraction, WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';

interface WebuiInteractionChannelEndpoints<TResolutionRequest> {
    pending(id: string): Promise<ConversationPendingInteractionResponse>;
    resolve(id: string, taskId: string, request: TResolutionRequest): Promise<ConversationInteractionResolutionResponse>;
}

interface WebuiChatInteractionEndpoints {
    askUser: WebuiInteractionChannelEndpoints<AskUserInteractionResolutionRequest>;
    vaultSecretRequest: WebuiInteractionChannelEndpoints<SecretPromptInteractionResolutionRequest>;
    toolApproval: WebuiInteractionChannelEndpoints<ToolApprovalInteractionResolutionRequest>;
    attentionRendered(id: string, request: ConversationAttentionRenderedRequest): Promise<void>;
    focus(id: string, focusNonce: string): Promise<ConversationInteractionFocusResponse>;
}

const createChannel = <TResolutionRequest>(api: ApiClientContext, paths: WebuiConversationPaths, interaction: WebuiConversationInteraction, serializeResolution: (request: TResolutionRequest) => JsonObject): WebuiInteractionChannelEndpoints<TResolutionRequest> => ({
    pending: async (id): Promise<ConversationPendingInteractionResponse> => decodePendingInteraction(await api.get(paths.interactionsPending(id, interaction))),
    resolve: async (id, taskId, request): Promise<ConversationInteractionResolutionResponse> => decodeInteractionResolution(await api.post(paths.interactionsResolve(id, interaction, taskId), serializeResolution(request)))
});

const createWebuiChatInteractionEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiChatInteractionEndpoints => ({
    askUser: createChannel(api, paths, 'ask_user', serializeAskUserInteractionResolution),
    vaultSecretRequest: createChannel(api, paths, 'vault_secret_request', serializeSecretPromptInteractionResolution),
    toolApproval: createChannel(api, paths, 'tool_approval', serializeToolApprovalInteractionResolution),
    attentionRendered: async (id, request): Promise<void> => {
        decodeNoContentResponse(await api.post(paths.attentionRendered(id), serializeConversationAttentionRendered(request)), 'Conversation attention rendered response');
    },
    focus: async (id, focusNonce): Promise<ConversationInteractionFocusResponse> => decodeInteractionFocus(await api.get(paths.interactionFocus(id, focusNonce)))
});

export { createWebuiChatInteractionEndpoints };
export type { WebuiChatInteractionEndpoints, WebuiInteractionChannelEndpoints };
