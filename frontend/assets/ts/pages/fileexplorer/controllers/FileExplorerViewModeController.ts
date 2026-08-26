/* SoAI - File explorer page control layer view mode controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerViewModeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { ViewModeController, type ViewMode } from '@core/uiprimitives/viewmode/public.ts';

type FileExplorerViewMode = Extract<ViewMode, 'list' | 'icons'>;

const VIEW_MODE_STORAGE_KEY = 'soai.fileExplorer.viewMode';

interface FileExplorerViewModeLabels {
    list: string;
    icons: string;
}

interface FileExplorerViewModeControllerDependencies {
    root: HTMLElement;
    button: HTMLButtonElement;
    sortSelect: HTMLSelectElement;
    sortShell: HTMLElement;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    labels: FileExplorerViewModeLabels;
    prepareCollectionViewModeChange: () => void;
    reapplyCollection: () => void;
    onActionsChanged: () => void;
}

class FileExplorerViewModeController {
    readonly #sortSelect: HTMLSelectElement;
    readonly #controller: ViewModeController;

    constructor(dependencies: FileExplorerViewModeControllerDependencies) {
        const initial = dependencies.root.dataset['viewMode'];
        if (initial !== 'list' && initial !== 'icons') {
            throw new Error('File Explorer root element is missing a valid data-view-mode attribute');
        }
        this.#sortSelect = dependencies.sortSelect;
        this.#controller = new ViewModeController({
            root: dependencies.root,
            button: dependencies.button,
            modes: ['list', 'icons'],
            activeMode: initial,
            storageKey: VIEW_MODE_STORAGE_KEY,
            labels: {
                cards: dependencies.labels.icons,
                list: dependencies.labels.list,
                icons: dependencies.labels.icons
            },
            icons: {
                cards: 'dashboard',
                list: 'view-list',
                icons: 'dashboard'
            },
            getIconSync: dependencies.getIconSync,
            onModeChanging: () => dependencies.prepareCollectionViewModeChange(),
            onModeChanged: (mode) => {
                this.#sortSelect.hidden = mode !== 'icons';
                dependencies.sortShell.classList.toggle('u-hidden', mode !== 'icons' || dependencies.root.classList.contains('is-selection-mode'));
                dependencies.onActionsChanged();
                dependencies.reapplyCollection();
            }
        });
        this.#sortSelect.hidden = initial !== 'icons';
        dependencies.sortShell.classList.toggle('u-hidden', initial !== 'icons' || dependencies.root.classList.contains('is-selection-mode'));
    }

    getMode(): FileExplorerViewMode {
        const mode = this.#controller.getMode();
        if (mode !== 'list' && mode !== 'icons') {
            throw new Error('File Explorer view mode controller returned an unsupported mode');
        }
        return mode;
    }

    toggle(): void {
        this.#controller.toggle();
    }
}

export { FileExplorerViewModeController, VIEW_MODE_STORAGE_KEY };
export type { FileExplorerViewMode };
