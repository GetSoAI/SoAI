/* SoAI - Tasks feature mappers [frontend/assets/ts/features/tasks/taskmanagerstore/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { PluginUpdateContext } from '@features/tasks/taskmanagerstore/contracts.ts';
import { toUpperCaseValue } from '@features/tasks/taskmanagerstore/guards.ts';

const coercePluginEntries = (value: JsonValue | null | undefined): PluginEntry[] => {
    const toPluginEntry = (candidate: JsonValue | null | undefined): PluginEntry | null => {
        if (!isObject(candidate) || isArray(candidate)) {
            return null;
        }
        const name = candidate['name'];
        const displayName = candidate['displayName'];
        const identifier = candidate['identifier'];
        const plugin = candidate['plugin'];
        const state = candidate['state'];
        const isPersistent = candidate['isPersistent'];
        const syntheticKey = candidate['__pluginKey'];
        const syntheticFlag = candidate['__synthetic'];

        return {
            name: isString(name) ? name : undefined,
            displayName: isString(displayName) ? displayName : undefined,
            identifier: isString(identifier) ? identifier : undefined,
            plugin: isString(plugin) ? plugin : undefined,
            state: isString(state) ? state : undefined,
            isPersistent: typeof isPersistent === 'boolean' ? isPersistent : undefined,
            __pluginKey: isString(syntheticKey) ? syntheticKey : undefined,
            __synthetic: typeof syntheticFlag === 'boolean' ? syntheticFlag : undefined
        };
    };

    const rawList = isArray(value)
        ? value
        : (() => {
              if (!isObject(value)) {
                  return [];
              }
              const nested = value['value'];
              return isArray(nested) ? nested : [];
          })();

    const entries: PluginEntry[] = [];
    for (const item of rawList) {
        const entry = toPluginEntry(item);
        if (entry) {
            entries.push(entry);
        }
    }
    return entries;
};

const buildPluginSnapshotSignature = (plugins: PluginEntry[], context: PluginUpdateContext): string => {
    return plugins
        .map((plugin) => {
            const key = context.pluginKey(plugin);
            if (!key) return '';
            const state = toUpperCaseValue(plugin.state || '');
            const name = toTrimmedStringOrNull(plugin.name) || '';
            const displayName = toTrimmedStringOrNull(plugin.displayName) || '';
            const identifier = toTrimmedStringOrNull(plugin.identifier) || '';
            return `${key}|${state}|${name}|${displayName}|${identifier}`;
        })
        .filter((signature) => signature)
        .sort((left, right) => left.localeCompare(right, 'en'))
        .join(';;');
};

export { buildPluginSnapshotSignature, coercePluginEntries };
