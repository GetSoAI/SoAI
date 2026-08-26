/* SoAI - Shared realtime default resource groups [frontend/assets/ts/core/realtime/streammanager/subscriptions/defaultResourceGroups.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CAPS, HARDWARE, HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, LOGS_CORE, METRICS, MODELS, PLUGINS, STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import type { BundleDefinitionConfig } from '@core/types/streamTypes.ts';

const BUNDLE_STATE_PREFIX = 'stream.bundle.';

const DEFAULT_BUNDLES: Array<[string, BundleDefinitionConfig]> = [
    [
        'dashboard',
        {
            resources: {
                status: STATUS,
                metrics: METRICS,
                hardware: HARDWARE,
                plugins: PLUGINS,
                models: MODELS
            }
        }
    ],
    [
        'hardware',
        {
            resources: {
                snapshot: HARDWARE,
                metrics: METRICS,
                gpuCapabilities: HARDWARE_GPU_CAPABILITIES,
                gpuSlots: HARDWARE_GPU_SLOTS,
                soaibenchRuns: HARDWARE_GPU_SOAIBENCH_RUNS,
                processes: HARDWARE_PROCESSES
            }
        }
    ],
    ['metrics', { resources: { metrics: METRICS } }],
    ['catalog', { resources: { models: MODELS, plugins: PLUGINS, hardware: HARDWARE, capabilities: CAPS } }],
    ['chat', { stateKey: `${BUNDLE_STATE_PREFIX}catalog`, resources: { models: MODELS } }],
    [
        'detached',
        {
            resources: {
                status: STATUS,
                metrics: METRICS,
                hardware: HARDWARE,
                plugins: PLUGINS,
                models: MODELS,
                logs: LOGS_CORE
            }
        }
    ],
    ['logs', { resources: { entries: LOGS_CORE } }]
];

export { BUNDLE_STATE_PREFIX, DEFAULT_BUNDLES };
