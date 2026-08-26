/* SoAI - Shared settings titlebar action markup [frontend/assets/ts/core/settings/titlebarActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { securityApi } from '@core/security/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';

type SettingsTitlebarAddButtonOptions = {
    id: string;
    action: string;
    label: JsonValue;
    disabled?: boolean | undefined;
};

type SettingsTitlebarRefreshButtonOptions = {
    action: string;
    label: JsonValue;
    id?: string | undefined;
};

const renderSettingsTitlebarAddButton = (options: SettingsTitlebarAddButtonOptions): string => {
    const label = securityApi.escapeHtml(options.label);
    const labelAttribute = securityApi.escapeAttribute(options.label);
    const icon = renderIconSlot(getIconSync('add', { size: 14, strokeWidth: 1.6 }));
    return `<button type="button" id="${securityApi.escapeAttribute(options.id)}" data-action="${securityApi.escapeAttribute(options.action)}" class="ui-button ui-button--titlebar ui-variant-accent"${renderControlDisabledAttributes(options.disabled === true)} aria-label="${labelAttribute}" data-tooltip="${labelAttribute}">${icon}<span>${label}</span></button>`;
};

const renderSettingsTitlebarRefreshButton = (options: SettingsTitlebarRefreshButtonOptions): string => {
    const label = securityApi.escapeHtml(options.label);
    const labelAttribute = securityApi.escapeAttribute(options.label);
    const idAttribute = options.id ? ` id="${securityApi.escapeAttribute(options.id)}"` : '';
    const icon = renderIconSlot(getIconSync('refresh', { size: 14, strokeWidth: 1.6 }));
    return `<button type="button"${idAttribute} data-action="${securityApi.escapeAttribute(options.action)}" class="ui-button ui-button--titlebar ui-variant-neutral" aria-label="${labelAttribute}" data-tooltip="${labelAttribute}">${icon}<span>${label}</span></button>`;
};

export { renderSettingsTitlebarAddButton, renderSettingsTitlebarRefreshButton };
