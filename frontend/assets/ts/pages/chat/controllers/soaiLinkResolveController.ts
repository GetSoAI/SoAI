/* SoAI - Chat SoAI link resolve controller [frontend/assets/ts/pages/chat/controllers/soaiLinkResolveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import type { SoaiLinkResolveResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { isAbortError } from '@core/errors/abort.ts';
import type { ChatPageApi } from '@features/chat/public.ts';

type ResolveSoaiLinkDraftRecordsArguments = Readonly<{
    api: ChatPageApi;
    conversationId: string;
    rawText: string;
    signal: AbortSignal;
    boundaryName: string;
}>;

const resolveSoaiLinkDraftRecordsWithNotification = async (inputArguments: ResolveSoaiLinkDraftRecordsArguments): Promise<SoaiLinkResolveResponse | null> => {
    const response = await handleApiResult(inputArguments.api.webui.chat.soaiLinks.resolve(inputArguments.conversationId, { rawText: inputArguments.rawText }, { signal: inputArguments.signal }), {
        boundaryName: inputArguments.boundaryName,
        silent: false,
        notifyOnError: true,
        logErrors: false,
        rethrow: (error) => isAbortError(error)
    });
    return response;
};

export { resolveSoaiLinkDraftRecordsWithNotification };
