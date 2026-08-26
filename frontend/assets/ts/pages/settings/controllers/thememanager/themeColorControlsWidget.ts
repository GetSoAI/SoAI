/* SoAI - Settings theme color controls widget [frontend/assets/ts/pages/settings/controllers/thememanager/themeColorControlsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const SOLID_BACKGROUND_PICKER_FALLBACK = '#000000';
const SURFACE_COLOR_PICKER_FALLBACK = '#3f4a46';

const renderColorClearButton = (id: string, label: string, visible: boolean): string => {
    const hiddenClass = visible ? '' : ' u-hidden';
    const ariaHidden = visible ? 'false' : 'true';
    return `<button type="button" id="${id}" class="ui-button ui-button--sm ui-variant-danger${hiddenClass}" aria-hidden="${ariaHidden}" aria-label="${label}" data-tooltip="${label}">${label}</button>`;
};

export { SOLID_BACKGROUND_PICKER_FALLBACK, SURFACE_COLOR_PICKER_FALLBACK, renderColorClearButton };
