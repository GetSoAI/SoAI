/* SoAI - Prompts page save dirty state manager [frontend/assets/ts/pages/prompts/controllers/page/saveDirtyStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';

type PromptsSaveDirtyHost = PromptsRuntimeContext;

const hasPromptCardEditChanges = (host: PromptsSaveDirtyHost): boolean => {
    const promptId = host.state.editingPromptId;
    if (!promptId) {
        return false;
    }
    if (host.state.draftPromptId === promptId) {
        return true;
    }
    const prompt = host.operations.findPromptById(promptId);
    if (!prompt) {
        return false;
    }
    const cardCandidate = host.owners.pageDom.optional(`.prompt-card[data-prompt-id="${promptId}"], .prompts-list-row[data-prompt-id="${promptId}"]`);
    const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
    if (!card) {
        return false;
    }
    const nameCandidate = host.owners.pageDom.optional('input[data-field="name"]', card);
    const contentCandidate = host.owners.pageDom.optional('textarea[data-field="content"]', card);
    if (!(nameCandidate instanceof HTMLInputElement)) {
        return false;
    }
    if (!(contentCandidate instanceof HTMLTextAreaElement)) {
        return false;
    }
    const nextName = readTrimmedInputValue(nameCandidate);
    const nextContent = contentCandidate.value;
    const nextColor = host.components.colorToolkit.normalize(card.dataset['selectedColor'] ?? null);

    const baselineName = toTrimmedString(prompt.name);
    const baselineContent = prompt.content;
    const baselineColor = host.components.colorToolkit.normalize(prompt.color);

    return nextName !== baselineName || nextContent !== baselineContent || nextColor !== baselineColor;
};

const hasPromptModalEditChanges = (host: PromptsSaveDirtyHost): boolean => {
    void host;
    return requireContentPreviewModalService().hasTextDraftChanges();
};

export { hasPromptCardEditChanges, hasPromptModalEditChanges };
