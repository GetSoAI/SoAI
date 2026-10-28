/* SoAI - Prompts picker prompt preview host bridge [frontend/assets/ts/features/prompts/picker/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptResponse } from '@core/api/contracts/promptContracts.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { PromptRecord } from '@features/prompts/promptRecords.ts';
import type { PromptPreviewHost } from '@features/prompts/promptPreview.ts';
import type { PromptsPickerPreviewHost } from '@features/prompts/picker/types.ts';

interface PromptsPickerPreviewHostOptions {
    promptsApi: PromptPreviewHost['promptsApi'];
    getDocument(): Document;
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptResponse): PromptRecord;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

const createPromptsPickerPreviewHost = (options: PromptsPickerPreviewHostOptions): PromptsPickerPreviewHost => ({
    promptsApi: options.promptsApi,
    findPromptById: (id) => options.findPromptById(id),
    upsertPromptRecord: (record) => options.upsertPromptRecord(record),
    requireModalElement: (id) => requireModalPresenter().requireElement(id),
    getDocument: () => options.getDocument(),
    showNotification: (message, type, duration) => options.showNotification(message, type ?? 'info', duration)
});

export { createPromptsPickerPreviewHost };
