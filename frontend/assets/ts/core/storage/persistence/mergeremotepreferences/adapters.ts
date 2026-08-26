/* SoAI - Shared frontend storage persistence merge remote preferences adapters [frontend/assets/ts/core/storage/persistence/mergeremotepreferences/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeStringArray } from '@core/storage/normalization.ts';
import type { HardwareCache, LogsCache, StorageCache, TerminalCache } from '@core/storage/persistence/mergeremotepreferences/types.ts';
import { isJsonObject, isJsonValue, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isNumber, isObject } from '@core/typeGuards.ts';

interface HardwarePatchDependencies {
    clone: <T>(value: T) => T;
}

interface MiscMergeDependencies {
    defaultsMisc: StorageCache['misc'];
    internalRemoteKeys: ReadonlySet<string>;
}

const applyLogsPatch = (patch: JsonValue | undefined, target: LogsCache): void => {
    if (!isObject(patch)) {
        return;
    }

    const lineLimit = patch['line_limit'];
    if (isNumber(lineLimit) && Number.isFinite(lineLimit)) {
        target.lineLimit = lineLimit;
    }

    const textZoom = patch['text_zoom'];
    if (isNumber(textZoom) && Number.isFinite(textZoom)) {
        target.textZoom = textZoom;
    }
};

const applySearchPatch = (patch: JsonValue | undefined, target: StorageCache['search']): void => {
    if (!isObject(patch)) {
        return;
    }

    const recent = patch['recent'];
    if (isArray(recent)) {
        target.recent = normalizeStringArray(recent, 50);
    }
};

const applyTerminalPatch = (patch: JsonValue | undefined, target: TerminalCache): void => {
    if (!isObject(patch)) {
        return;
    }

    const textZoom = patch['text_zoom'];
    if (isNumber(textZoom) && Number.isFinite(textZoom)) {
        target.textZoom = textZoom;
    }
};

const applyHardwarePatch = (patch: JsonValue | undefined, target: HardwareCache, dependencies: HardwarePatchDependencies): void => {
    if (!isObject(patch)) {
        return;
    }

    const refreshInterval = patch['refresh_interval'];
    if (isNumber(refreshInterval) && Number.isFinite(refreshInterval)) {
        target.refreshInterval = refreshInterval;
    }

    const showGraphs = patch['show_graphs'];
    if (isBoolean(showGraphs)) {
        target.showGraphs = showGraphs;
    }

    const graphTimeRange = patch['graph_time_range'];
    if (isNumber(graphTimeRange) && Number.isFinite(graphTimeRange)) {
        target.graphTimeRange = graphTimeRange;
    }

    const gpuSettings = patch['gpu_settings'];
    if (isJsonObject(gpuSettings)) {
        target.gpuSettings = dependencies.clone(gpuSettings);
    }
};

const applyWizardPatch = (patch: JsonValue | undefined, target: StorageCache['wizard']): void => {
    if (!isObject(patch)) {
        return;
    }

    const completed = patch['completed'];
    if (isBoolean(completed)) {
        target.completed = completed;
    }
};

const applySettingsPatch = (patch: JsonValue | undefined, target: StorageCache['settings']): void => {
    if (!isObject(patch)) {
        return;
    }

    const advancedMode = patch['advanced_mode'];
    if (isBoolean(advancedMode)) {
        target.advancedMode = advancedMode;
    }
};

const mergeMisc = (remote: JsonValue, dependencies: MiscMergeDependencies): JsonRecord => {
    if (!isObject(remote)) {
        throw new Error('Remote preferences payload must be an object');
    }

    const misc: JsonRecord = {};
    const mergeSource = (source: JsonValue | undefined): void => {
        if (!isObject(source)) {
            return;
        }
        for (const [key, value] of Object.entries(source)) {
            if (isJsonValue(value)) {
                misc[key] = value;
            }
        }
    };

    mergeSource(dependencies.defaultsMisc);
    mergeSource(remote['misc']);
    mergeSource(remote['custom']);
    mergeSource(remote['miscellaneous']);

    for (const key of Object.keys(remote)) {
        if (!key.startsWith('soai_')) {
            continue;
        }
        if (key in misc) {
            continue;
        }
        if (dependencies.internalRemoteKeys.has(key)) {
            continue;
        }
        const value = remote[key];
        if (isJsonValue(value)) {
            misc[key] = value;
        }
    }

    return misc;
};

export { applyHardwarePatch, applyLogsPatch, applySearchPatch, applySettingsPatch, applyTerminalPatch, applyWizardPatch, mergeMisc };
