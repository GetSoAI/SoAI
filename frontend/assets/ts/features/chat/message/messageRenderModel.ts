/* SoAI - Chat feature message render model [frontend/assets/ts/features/chat/message/messageRenderModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';

type ChatMessageRenderModel = {
    message: ChatMessage;
    conversationId: string;
    index: number;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
    presentation: ChatMessageRenderPresentation;
    forceSettledAssistantActions?: boolean;
    forceSettledAssistantBody?: boolean;
};

export type { ChatMessageRenderModel };
