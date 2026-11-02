/* SoAI - Shared DOM focus target availability [frontend/assets/ts/core/dom/focusTarget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isAvailableFocusTarget = (element: HTMLElement): boolean => !element.matches(':disabled') && element.closest('[hidden], .u-hidden, [aria-hidden="true"], [inert]') === null;

export { isAvailableFocusTarget };
