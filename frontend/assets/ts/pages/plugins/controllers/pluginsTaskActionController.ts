/* SoAI - Plugins page task action controller [frontend/assets/ts/pages/plugins/controllers/pluginsTaskActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import { resolveTaskOperationFailureText } from '@core/tasks/operationText.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import { isObject } from '@core/typeGuards.ts';

interface PluginsTaskActionControllerHost {
    getStreamTracker(scope: string): {
        track(key: string, stream: StreamActionHandle): void;
        release(key: string): void;
    };
    startTaskAction(endpoint: string, options: { method: string }): Promise<StreamActionHandle>;
    runPageTask(taskKey: string, task: () => Promise<JsonValue>, options: { displayName: string; rethrow: boolean }): Promise<JsonValue>;
}

class PluginsTaskActionController {
    #host: PluginsTaskActionControllerHost;

    constructor(host: PluginsTaskActionControllerHost) {
        this.#host = host;
    }

    async runPluginTaskAction(
        taskKey: string,
        endpoint: string,
        options: {
            pluginName: string;
            displayName: string;
            onAccepted?: (taskId: string) => void;
        }
    ): Promise<Record<string, JsonValue> | null> {
        const tracker = this.#host.getStreamTracker('plugins.actions');
        const result = await this.#host.runPageTask(
            taskKey,
            async () => {
                const stream = await this.#host.startTaskAction(endpoint, { method: 'POST' });
                if (!stream) {
                    throw new Error('Failed to start plugin task');
                }
                if (!stream.accepted) {
                    throw new Error('Plugin task action did not expose accepted task ownership');
                }
                const acceptedTaskId = await stream.accepted;
                options.onAccepted?.(acceptedTaskId);
                const settled = await settleTrackedTaskStream({
                    tracker,
                    stream,
                    keyPrefix: `${taskKey}-${options.pluginName}`,
                    failMessage: resolveTaskOperationFailureText('pluginTask')
                });
                if (settled.cancelled || settled.detached) {
                    return { cancelled: settled.cancelled, detached: settled.detached };
                }
                if (!settled.record) {
                    throw new Error('Plugin task did not return a response record');
                }
                return settled.record;
            },
            { displayName: options.displayName, rethrow: false }
        );
        if (!result || !isObject(result)) {
            return null;
        }
        if (result['cancelled'] === true || result['detached'] === true) {
            return null;
        }
        return result;
    }
}

export { PluginsTaskActionController };
export type { PluginsTaskActionControllerHost };
