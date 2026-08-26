/* SoAI - Models page control layer model enabled toggle controller [frontend/assets/ts/pages/models/controllers/page/modelEnabledToggleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelData } from '@core/types/modelTypes.ts';
import { resolveModelEnabledToggleTarget } from '@pages/models/controllers/modelsModelProperties.ts';

interface ModelEnabledToggleState {
    getPendingToggleTarget(model: ModelData): boolean | null;
    setPendingToggleTarget(targetKey: string, enabled: boolean): void;
    clearPendingToggleTarget(targetKey: string): void;
}

const createModelEnabledToggleState = (): ModelEnabledToggleState => {
    const pendingToggleTargets = new Map<string, boolean>();
    return {
        getPendingToggleTarget: (model) => {
            const target = resolveModelEnabledToggleTarget(model);
            if (!target) {
                return null;
            }
            return pendingToggleTargets.get(target.targetKey) ?? null;
        },
        setPendingToggleTarget: (targetKey, enabled) => {
            if (!targetKey) {
                return;
            }
            pendingToggleTargets.set(targetKey, enabled);
        },
        clearPendingToggleTarget: (targetKey) => {
            if (!targetKey) {
                return;
            }
            pendingToggleTargets.delete(targetKey);
        }
    };
};

export { createModelEnabledToggleState };
export type { ModelEnabledToggleState };
