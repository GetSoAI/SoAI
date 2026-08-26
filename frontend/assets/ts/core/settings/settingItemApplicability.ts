/* SoAI - Settings item applicability contract [frontend/assets/ts/core/settings/settingItemApplicability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const setSettingItemApplicable = (item: HTMLElement, applicable: boolean): void => {
    item.hidden = !applicable;
};

const isSettingItemApplicable = (item: Element): boolean => !item.hasAttribute('hidden');

export { isSettingItemApplicable, setSettingItemApplicable };
