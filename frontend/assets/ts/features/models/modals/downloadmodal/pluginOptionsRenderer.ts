/* SoAI - Models feature plugin options renderer [frontend/assets/ts/features/models/modals/downloadmodal/pluginOptionsRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceSelectOptions, type SelectOptionDefinition } from '@core/dom/selectOptions.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isObject } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';
import { resolvePluginUnavailableReason, type PluginUnavailableMode } from '@features/models/modals/downloadmodal/pluginAvailability.ts';

interface RenderPluginOptionsController {
    host: DownloadModalHost;
}

const uppercaseInitial = (value: string): string => {
    const normalized = toTrimmedString(value);
    if (!normalized) {
        return '';
    }
    return `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}`;
};

const lowercaseInitial = (value: string): string => {
    const normalized = toTrimmedString(value);
    if (!normalized) {
        return '';
    }
    return `${normalized.charAt(0).toLowerCase()}${normalized.slice(1)}`;
};

const renderPluginOptions = (controller: RenderPluginOptionsController, select: Element, plugins: PluginRecord[], placeholder: string, checkOperational: (plugin: PluginRecord) => boolean, mode: PluginUnavailableMode): void => {
    if (!(select instanceof HTMLSelectElement)) {
        throw new TypeError('Plugin options renderer requires an HTMLSelectElement');
    }
    const selectElement = select;
    const currentValue = selectElement.value;
    const options: SelectOptionDefinition[] = [{ value: '', label: placeholder }];
    const enabledValues = new Set<string>();
    for (const plugin of plugins) {
        const value = toTrimmedString(plugin?.name);
        if (!value) continue;
        const isOperational = checkOperational(plugin);
        const displayName = isObject(plugin) ? plugin.displayName : null;
        const sourceLabel = typeof displayName === 'string' && displayName.trim() ? displayName : String(plugin.name ?? value);
        const baseLabel = uppercaseInitial(sourceLabel) || uppercaseInitial(value);
        if (isOperational) enabledValues.add(value);
        const reason = isOperational ? '' : lowercaseInitial(resolvePluginUnavailableReason(plugin, mode));
        const label = isOperational ? baseLabel : `${baseLabel} (${reason})`;
        options.push({
            value,
            label,
            disabled: !isOperational
        });
    }
    replaceSelectOptions(selectElement, options);
    controller.host.view.setUIValue(select, currentValue && enabledValues.has(currentValue) ? currentValue : '', {
        attribute: 'value'
    });
};

export { renderPluginOptions };
