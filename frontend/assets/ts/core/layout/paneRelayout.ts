/* SoAI - Synchronous pane relayout signal for container-driven layouts [frontend/assets/ts/core/layout/paneRelayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const PANE_RELAYOUT_EVENT = 'soai:pane:relayout';

const dispatchPaneRelayout = (view: Window | null): void => {
    view?.dispatchEvent(new Event(PANE_RELAYOUT_EVENT));
};

export { PANE_RELAYOUT_EVENT, dispatchPaneRelayout };
