/* SoAI - Chat feature comparison turn render model [frontend/assets/ts/features/chat/comparisonTurnRenderModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatComparisonTurnInvalidReason } from '@features/chat/comparisonTurnMetadata.ts';

type ChatComparisonTurnRenderModel = {
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
    activeVariantIndex: number;
    variantCount: number;
    invalidReason: ChatComparisonTurnInvalidReason | null;
};

export type { ChatComparisonTurnRenderModel };
