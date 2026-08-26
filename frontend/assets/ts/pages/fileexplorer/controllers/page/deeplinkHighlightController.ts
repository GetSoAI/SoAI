/* SoAI - File explorer page control layer deeplink highlight controller [frontend/assets/ts/pages/fileexplorer/controllers/page/deeplinkHighlightController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/globalScope.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';

interface FileExplorerDeeplinkHighlightController {
    apply: () => void;
    clear: () => void;
}

interface FileExplorerDeeplinkHighlightDependencies {
    rowsBody: HTMLTableSectionElement;
    highlightPath: string | null;
}

const HIGHLIGHT_ROW_CLASS = 'file-explorer-row--deeplink-highlight';
const HIGHLIGHT_AUTO_CLEAR_MS = 12000;

const normalizeOptionalVirtualPath = (value: string | null): string | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    return toVirtualPath(trimmed);
};

const createFileExplorerDeeplinkHighlightController = (dependencies: FileExplorerDeeplinkHighlightDependencies): FileExplorerDeeplinkHighlightController => {
    const win = getWindow();
    let highlightPath: string | null = normalizeOptionalVirtualPath(dependencies.highlightPath);
    let highlightSequence = 0;
    let highlightScrolledSequence = -1;
    let highlightTimeoutId: number | null = null;

    const clearHighlightClasses = (): void => {
        for (const element of dom.resolveAll(`tr.${HIGHLIGHT_ROW_CLASS}`, dependencies.rowsBody)) {
            if (element instanceof HTMLElement) {
                element.classList.remove(HIGHLIGHT_ROW_CLASS);
            }
        }
    };

    const clear = (): void => {
        highlightSequence += 1;
        highlightScrolledSequence = -1;
        highlightPath = null;
        if (highlightTimeoutId !== null) {
            win.clearTimeout(highlightTimeoutId);
            highlightTimeoutId = null;
        }
        clearHighlightClasses();
    };

    const resolveRowForHighlight = (virtualPath: string): HTMLTableRowElement | null => {
        const selector = `button.file-explorer-open-btn[data-path="${CSS.escape(virtualPath)}"]`;
        const button = dom.resolve(selector, dependencies.rowsBody);
        if (!(button instanceof HTMLElement)) {
            return null;
        }
        const row = button.closest('tr');
        return row instanceof HTMLTableRowElement ? row : null;
    };

    const apply = (): void => {
        const targetPath = highlightPath;
        if (!targetPath) {
            return;
        }
        const row = resolveRowForHighlight(targetPath);
        if (!row) {
            return;
        }
        clearHighlightClasses();
        row.classList.add(HIGHLIGHT_ROW_CLASS);
        if (highlightScrolledSequence !== highlightSequence) {
            row.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' });
            highlightScrolledSequence = highlightSequence;
        }
        if (highlightTimeoutId === null) {
            const currentSequence = highlightSequence;
            highlightTimeoutId = win.setTimeout(() => {
                if (highlightSequence !== currentSequence) {
                    return;
                }
                clear();
            }, HIGHLIGHT_AUTO_CLEAR_MS);
        }
    };

    return { apply, clear };
};

export { createFileExplorerDeeplinkHighlightController };
