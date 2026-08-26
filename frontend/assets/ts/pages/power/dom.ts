/* SoAI - Power page DOM contracts [frontend/assets/ts/pages/power/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PowerUi } from '@pages/power/types.ts';

export const requirePowerUi = (dependencies: { requireHTMLElement: (selector: string, context?: Element) => HTMLElement; optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null }): PowerUi => {
    const root = dependencies.requireHTMLElement('[data-section="power"]');
    const grid = dependencies.requireHTMLElement('#power-grid', root);
    const applicationRestartNotice = dependencies.optionalHTMLElement('#power-restart-notice-restartApplication', root);
    const applicationRestartOptions = dependencies.optionalHTMLElement('[data-action-key="restartApplication"] .power-options', root);
    const systemRestartNotice = dependencies.optionalHTMLElement('#power-restart-notice-rebootSystem', root);
    const systemRestartOptions = dependencies.optionalHTMLElement('[data-action-key="rebootSystem"] .power-options', root);

    return { root, grid, applicationRestartNotice, applicationRestartOptions, systemRestartNotice, systemRestartOptions };
};

export const optionalPowerRoot = (dependencies: { optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null }): HTMLElement | null => dependencies.optionalHTMLElement('[data-section="power"]');
