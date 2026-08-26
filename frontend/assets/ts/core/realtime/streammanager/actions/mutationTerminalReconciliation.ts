/* SoAI - Accepted plugin mutation terminal reconciliation [frontend/assets/ts/core/realtime/streammanager/actions/mutationTerminalReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { TaskTerminalEvent } from '@core/realtime/streammanager/types.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const PLUGIN_MUTATION_TYPES = new Set(['backend-install', 'backend-remove', 'backend-update', 'plugin-clone']);

const reconcilePluginMutationTerminal = async (event: TaskTerminalEvent, refresh: (resourceName: string) => Promise<JsonValue | null>): Promise<boolean> => {
    const operationType = toTrimmedString(event.meta?.type);
    if (!operationType || !PLUGIN_MUTATION_TYPES.has(operationType)) return false;
    await Promise.all([refresh(PLUGINS), refresh(MODELS)]);
    return true;
};

export { reconcilePluginMutationTerminal };
