/* SoAI - Runtime guards/parsers for chat stream kernel services [frontend/assets/ts/core/chat/streamGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { ChatStreamServiceLifecycleContract } from '@core/chat/protocols.ts';

type ChatStreamServiceGuardCandidate = ChatStreamServiceLifecycleContract | null;

const isChatStreamServiceLifecycleContract = (value: ChatStreamServiceGuardCandidate): value is ChatStreamServiceLifecycleContract => {
    return isObject(value) && 'initialize' in value && 'dispose' in value && isFunction(value.initialize) && isFunction(value.dispose);
};

export { isChatStreamServiceLifecycleContract };
