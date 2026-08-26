/* SoAI - Model detail page control layer save controller [frontend/assets/ts/pages/modeldetail/controllers/page/saveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import { hasOpenAICapabilityOverrideChanges, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import { saveModelDetailOpenAICapabilities, saveModelDetailParameters, type ModelDetailActionsHost } from '@pages/modeldetail/controllers/page/actionEffects.ts';

interface ModelDetailSaveControllerDependencies {
    actions: ModelDetailActionsHost;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
}

const createModelDetailSaveController = (dependencies: ModelDetailSaveControllerDependencies): SaveController =>
    createSaveController({
        headerContextId: 'model-detail',
        headerPriority: SAVE_HEADER_PRIORITY_PAGE,
        requestContextLabel: 'Model detail save',
        units: [
            {
                id: 'model-detail',
                hasChanges: () => dependencies.actions.parameterView.hasParameterChanges(),
                isValid: () => dependencies.actions.parameterView.areParametersValid(),
                save: async () => {
                    await saveModelDetailParameters(dependencies.actions);
                }
            },
            {
                id: 'model-detail-openai-capabilities',
                hasChanges: () => hasOpenAICapabilityOverrideChanges(dependencies.getOpenAICapabilityState()),
                save: async () => {
                    await saveModelDetailOpenAICapabilities(dependencies.actions);
                }
            }
        ]
    });

export { createModelDetailSaveController };
export type { ModelDetailSaveControllerDependencies };
