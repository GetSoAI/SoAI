/* SoAI - Shared UI icon service constants [frontend/assets/ts/core/ui/icons/iconservice/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconDefaultOptions } from '@core/ui/icons/iconservice/types.ts';

const DEFAULT_ICON_SIZE = 24;
const DEFAULT_ICON_STROKE = 1.5;

const MISSING_ICON_GLYPH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">' + '<rect x="3.5" y="3.5" width="17" height="17" rx="2" />' + '<path d="M9 9.2c0-1.3 1.1-2.4 2.5-2.4h.7c1.3 0 2.3 1 2.3 2.2 0 .9-.5 1.6-1.3 2.1-.7.4-1.2 1-1.2 2.1v.3" />' + '<path d="M12 17.3h.01" />' + '</svg>';

const ICON_DEFAULTS: Readonly<Partial<Record<IconName, IconDefaultOptions>>> = (() => {
    const defaults: Partial<Record<IconName, IconDefaultOptions>> = {};

    const setMany = (icons: readonly IconName[], size: number, strokeWidth: number): void => {
        for (const icon of icons) {
            defaults[icon] = { size, strokeWidth };
        }
    };

    setMany(['chevron-up', 'chevron-down', 'chevron-left', 'chevron-right', 'close', 'menu', 'refresh', 'search', 'add', 'minus', 'external-link', 'sparkle', 'prompt'], 16, 1.5);

    setMany(['power', 'provider', 'settings', 'tasks', 'plan', 'error', 'error-modal', 'success-modal', 'warning-modal', 'danger-modal', 'info-modal', 'download', 'window', 'select', 'model-virtual', 'warning', 'plugin', 'filter'], 24, 1.5);

    setMany(['model-default', 'device-network', 'device-storage', 'device-cpu', 'device-gpu'], 20, 1.5);

    setMany(['file-generic', 'file-image', 'file-video', 'file-audio', 'file-text', 'file-code', 'file-archive', 'file-pdf', 'file-config', 'file-database', 'file-font', 'file-binary', 'file-spreadsheet', 'file-document', 'file-presentation', 'file-disc', 'file-key', 'file-vector', 'file-3d', 'file-notebook', 'file-log', 'file-lock', 'file-data', 'file-ebook', 'file-subtitle', 'file-map', 'file-exe', 'folder-archive'], 16, 1.5);

    setMany(['delete', 'rename', 'storage-eject'], 12, 1.5);
    defaults['clock'] = { size: 12, strokeWidth: 1.7 };
    defaults['info'] = { size: 24, strokeWidth: 2 };
    defaults['stop'] = { size: 18, strokeWidth: 1.5 };
    setMany(['connection-offline', 'application-power-cycle', 'system-power-cycle'], 68, 1.5);

    defaults['restart'] = { size: 48, strokeWidth: 1.5 };
    defaults['suspend'] = { size: 48, strokeWidth: 1.5 };
    defaults['hibernate'] = { size: 48, strokeWidth: 1.5 };
    defaults['copy'] = { size: 10, strokeWidth: 1 };

    return defaults;
})();

export { DEFAULT_ICON_SIZE, DEFAULT_ICON_STROKE, ICON_DEFAULTS, MISSING_ICON_GLYPH };
