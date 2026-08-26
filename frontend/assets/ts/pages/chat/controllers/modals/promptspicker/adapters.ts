/* SoAI - Chat prompts picker prompt preview host bridge [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptResponse } from '@core/api/contracts/promptContracts.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { ChatPromptsPickerPreviewHost } from '@pages/chat/controllers/modals/promptspicker/types.ts';

interface ChatPromptsPickerPreviewHostOptions {
    api: ChatPageApi;
    getDocument(): Document;
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptResponse): PromptRecord;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

const createChatPromptsPickerPreviewHost = (options: ChatPromptsPickerPreviewHostOptions): ChatPromptsPickerPreviewHost => ({
    promptsApi: options.api.webui.prompts,
    findPromptById: (id) => options.findPromptById(id),
    upsertPromptRecord: (record) => options.upsertPromptRecord(record),
    requireModalElement: (id) => requireModalPresenter().requireElement(id),
    getDocument: () => options.getDocument(),
    showNotification: (message, type, duration) => options.showNotification(message, type ?? 'info', duration)
});

export { createChatPromptsPickerPreviewHost };
