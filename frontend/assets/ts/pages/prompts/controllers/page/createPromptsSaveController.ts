/* SoAI - Prompts page card and modal save ownership [frontend/assets/ts/pages/prompts/controllers/page/createPromptsSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';
import { saveEditing } from '@pages/prompts/controllers/page/effects.ts';
import { hasPromptCardEditChanges, hasPromptModalEditChanges } from '@pages/prompts/controllers/page/saveDirtyStateManager.ts';
import { savePromptFromModal } from '@pages/prompts/controllers/page/service.ts';

const createPromptsSaveController = (runtime: PromptsRuntimeContext): SaveController =>
    createSaveController({
        headerContextId: 'prompts',
        headerPriority: SAVE_HEADER_PRIORITY_PAGE,
        requestContextLabel: 'Prompts save',
        units: [
            {
                id: 'prompts-card-edit',
                hasChanges: () => hasPromptCardEditChanges(runtime),
                save: async () => {
                    if (runtime.state.editingPromptId) await saveEditing(runtime, runtime.state.editingPromptId);
                }
            },
            {
                id: 'prompts-modal-edit',
                hasChanges: () => hasPromptModalEditChanges(runtime),
                save: async () => {
                    await savePromptFromModal(runtime);
                }
            }
        ]
    });

export { createPromptsSaveController };
