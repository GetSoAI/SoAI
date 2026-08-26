/* SoAI - File Explorer uploaded row reveal controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerUploadRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { scrollElementToScrollerCenter } from '@core/scroll.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import type { FileExplorerRecentUploadController } from '@pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts';

const UPLOAD_REVEAL_ROW_SELECTOR = (path: string): string => `tr[data-path="${CSS.escape(path)}"]`;

class FileExplorerUploadRevealController {
    readonly #rowsBody: HTMLTableSectionElement;
    readonly #recentUploads: FileExplorerRecentUploadController;

    constructor(dependencies: { rowsBody: HTMLTableSectionElement; recentUploads: FileExplorerRecentUploadController }) {
        this.#rowsBody = dependencies.rowsBody;
        this.#recentUploads = dependencies.recentUploads;
    }

    reveal(entries: readonly FileBrowserEntry[]): void {
        const paths = this.#recentUploads.resolveRevealPathsForEntries(entries);
        if (paths.length <= 0) {
            return;
        }
        const rows: HTMLTableRowElement[] = [];
        for (const path of paths) {
            rows.push(this.#requireRow(path));
        }
        const targetRow = rows[Math.floor((rows.length - 1) / 2)];
        if (!targetRow) {
            throw new Error('File Explorer uploaded entry reveal requires a target row');
        }
        scrollElementToScrollerCenter(this.#rowsBody, targetRow);
        this.#recentUploads.consumeRevealPaths(paths);
    }

    #requireRow(path: string): HTMLTableRowElement {
        const row = dom.resolve(UPLOAD_REVEAL_ROW_SELECTOR(path), this.#rowsBody);
        if (!(row instanceof HTMLTableRowElement)) {
            throw new Error('File Explorer uploaded entry reveal target is missing');
        }
        return row;
    }
}

export { FileExplorerUploadRevealController };
