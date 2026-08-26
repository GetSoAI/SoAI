/* SoAI - Terminal page DOM contracts [frontend/assets/ts/pages/terminal/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { TerminalUiRefs } from '@pages/terminal/types.ts';

export const requireTerminalRoot = (pageDom: PageDom): HTMLElement => pageDom.requireHTMLElement('#terminal-root');
export const requireTerminalShell = (pageDom: PageDom): HTMLElement => pageDom.requireHTMLElement('#terminal-shell');

export const optionalTerminalRoot = (pageDom: PageDom): HTMLElement | null => pageDom.optionalHTMLElement('#terminal-root');
export const optionalTerminalShell = (pageDom: PageDom): HTMLElement | null => pageDom.optionalHTMLElement('#terminal-shell');

export const requireTerminalUi = (pageDom: PageDom): TerminalUiRefs => {
    return {
        root: requireTerminalRoot(pageDom),
        shell: requireTerminalShell(pageDom)
    };
};
