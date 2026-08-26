/* SoAI - Prompts page prompt record manager [frontend/assets/ts/pages/prompts/controllers/page/promptRecordManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptRequest } from '@core/api/contracts/promptContracts.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { PromptsApiClient } from '@pages/prompts/contracts/promptsTypes.ts';
import type { PromptsPageSession } from '@pages/prompts/controllers/page/PromptsPageSession.ts';

interface PromptsApiHost {
    state: Pick<PromptsPageSession, 'promptsApi'>;
}

const requirePromptsApi = (host: PromptsApiHost): PromptsApiClient => {
    if (!host.state.promptsApi) {
        throw new Error('Prompts API is not available');
    }
    return host.state.promptsApi;
};

const createPromptRecord = async (host: PromptsApiHost, payload: PromptRequest, _context: string): Promise<PromptRecord> => {
    return await requirePromptsApi(host).create(payload);
};

const updatePromptRecord = async (host: PromptsApiHost, id: string | number, payload: PromptRequest, _context: string): Promise<PromptRecord> => {
    return await requirePromptsApi(host).update(String(id), payload);
};

export { createPromptRecord, requirePromptsApi, updatePromptRecord };
export type { PromptsApiHost };
