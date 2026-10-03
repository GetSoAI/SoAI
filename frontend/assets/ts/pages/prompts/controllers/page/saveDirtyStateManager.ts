/* SoAI - Prompts page save dirty state manager [frontend/assets/ts/pages/prompts/controllers/page/saveDirtyStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
    const editingDraft = host.state.editingDraft;
    if (!editingDraft || editingDraft.promptId !== promptId) return false;

    const baselineName = toTrimmedString(prompt.name);
    const baselineContent = prompt.content;
    const baselineColor = host.components.colorToolkit.normalize(prompt.color);

    return toTrimmedString(editingDraft.name) !== baselineName || editingDraft.content !== baselineContent || host.components.colorToolkit.normalize(editingDraft.color) !== baselineColor;
};

const hasPromptModalEditChanges = (host: PromptsSaveDirtyHost): boolean => {
    void host;
    return requireContentPreviewModalService().hasTextDraftChanges();
};

export { hasPromptCardEditChanges, hasPromptModalEditChanges };
