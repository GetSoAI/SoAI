/* SoAI - Shared layout sidebar state [frontend/assets/ts/core/layout/sidebar/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface SidebarState {
    collapsed: boolean;
    mobile: boolean;
    open: boolean;
    hideTerminal: boolean;
    hideModels: boolean;
    lastDesktopCollapsed: boolean;
    grantedActions: ReadonlySet<string>;
}

const createInitialSidebarState = (): SidebarState => ({
    collapsed: true,
    mobile: false,
    open: false,
    hideTerminal: false,
    hideModels: false,
    lastDesktopCollapsed: true,
    grantedActions: new Set()
});

export { createInitialSidebarState };
export type { SidebarState };
