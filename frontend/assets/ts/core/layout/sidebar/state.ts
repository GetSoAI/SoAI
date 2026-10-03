/* SoAI - Shared layout sidebar state [frontend/assets/ts/core/layout/sidebar/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface SidebarState {
    collapsed: boolean;
    peeking: boolean;
    mobile: boolean;
    open: boolean;
    lastDesktopCollapsed: boolean;
    grantedActions: ReadonlySet<string>;
    permissionsUnavailable: boolean;
}

const createInitialSidebarState = (): SidebarState => ({
    collapsed: true,
    peeking: false,
    mobile: false,
    open: false,
    lastDesktopCollapsed: true,
    grantedActions: new Set(),
    permissionsUnavailable: false
});

export { createInitialSidebarState };
export type { SidebarState };
