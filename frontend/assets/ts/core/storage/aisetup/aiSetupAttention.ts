/* SoAI - Shared storage AI setup items needing user attention [frontend/assets/ts/core/storage/aisetup/aiSetupAttention.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAiSetupModelReady, isAiSetupStateResumable, type AiSetupModel, type AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';

const hasSettledTask = (taskId: string | null, activeTaskIds: ReadonlySet<string>): boolean => taskId !== null && !activeTaskIds.has(taskId);

const needsAttention = (setup: AiSetupState, model: AiSetupModel, activeTaskIds: ReadonlySet<string>): boolean => {
    if (model.excluded || isAiSetupModelReady(model)) return false;
    if (model.source === 'cloud') return model.test.status === 'failed';
    if (model.modelId !== null || hasSettledTask(model.downloadTaskId, activeTaskIds)) return true;
    if (model.downloadTaskId !== null) return false;
    return setup.engine.backends.some((backend) => backend.pluginName === model.pluginName && !backend.excluded && hasSettledTask(backend.taskId, activeTaskIds));
};

const listAiSetupItemsNeedingAttention = (setup: AiSetupState | null, activeTaskIds: ReadonlySet<string>): string[] => {
    if (setup === null || !isAiSetupStateResumable(setup)) return [];
    const announced = new Set(setup.pendingToastShownFor);
    return setup.models.filter((model) => !announced.has(model.itemId) && needsAttention(setup, model, activeTaskIds)).map((model) => model.itemId);
};

export { listAiSetupItemsNeedingAttention };
