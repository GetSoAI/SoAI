/* SoAI - Shared routing cleanup [frontend/assets/ts/core/routing/pages/basepagelayout/cleanup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';

const cleanupBasePageLayoutTransientState = (state: BasePageLayoutState): void => {
    state.tabs?.destroy?.();
    state.ctaLinkDisposer?.();
    state.pageActionsMenu?.dispose();
    state.tabs = null;
    state.ctaLinkDisposer = null;
    state.pageActionsMenu = null;
    state.externalLinkTargets = null;
};

export { cleanupBasePageLayoutTransientState };
