/* SoAI - Shared chat parameters contracts [frontend/assets/ts/core/chat/parameters/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatUiParameters } from '@core/types/chatParameters.ts';

type ChatParameters = ChatUiParameters;

interface ChatParameterMeta {
    type: 'number';
    precision: number;
    min?: number;
    max?: number;
}

export type { ChatParameters, ChatParameterMeta };
