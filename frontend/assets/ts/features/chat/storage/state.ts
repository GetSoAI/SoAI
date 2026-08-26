/* SoAI - Chat feature storage state [frontend/assets/ts/features/chat/storage/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildChatPreferencesPayload } from '@core/chat/parameters/chatParameterDefaults.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';

const buildPreferencesSnapshot = (manager: Pick<ChatStorageManagerContract, 'state'>): JsonRecord => {
    return buildChatPreferencesPayload({
        parameters: manager.state.getParameters()
    });
};

export { buildPreferencesSnapshot };
