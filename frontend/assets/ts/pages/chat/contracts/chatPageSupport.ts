/* SoAI - Chat page support [frontend/assets/ts/pages/chat/contracts/chatPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const PAGE_ID = 'chat';
const PAGE_MODULE_ID = 'pages.ChatPage';

interface EnsureResourceStartedHost {
    ensureResourceStarted(resourceId: string): Promise<JsonValue> | JsonValue;
}

interface CloseableHandle {
    close(options?: JsonValue): JsonValue;
}

const isEnsureResourceStartedHost = <T>(value: T): value is T & EnsureResourceStartedHost => isObject(value) && 'ensureResourceStarted' in value && isFunction(value.ensureResourceStarted);

const isCloseableHandle = <T>(value: T): value is T & CloseableHandle => isObject(value) && 'close' in value && isFunction(value.close);

export { PAGE_ID, PAGE_MODULE_ID, isCloseableHandle, isEnsureResourceStartedHost };
