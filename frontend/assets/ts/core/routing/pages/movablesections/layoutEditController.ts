/* SoAI - Shared routing layout edit controller [frontend/assets/ts/core/routing/pages/movablesections/layoutEditController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHeaderEditController, type HeaderEditController } from '@core/headeredit/controller.ts';
import type { MovableSectionId } from '@core/routing/pages/movablesections/types.ts';
import type { MovableSectionLayout } from '@core/routing/pages/movablesections/service.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';

interface MovableLayoutEditControllerDependencies<TSectionId extends MovableSectionId> {
    layout: MovableSectionLayout<TSectionId>;
    contextId: string;
    saveUnitId: string;
    requestContextLabel: string;
    isCustomizationDisabled: () => boolean;
}

class MovableLayoutEditController<TSectionId extends MovableSectionId> {
    readonly #layout: MovableSectionLayout<TSectionId>;
    readonly #contextId: string;
    readonly #saveUnitId: string;
    readonly #requestContextLabel: string;
    readonly #isCustomizationDisabled: () => boolean;
    #save: SaveController | null = null;
    #edit: HeaderEditController | null = null;
    #editing = false;
    #initialized = false;

    constructor(dependencies: MovableLayoutEditControllerDependencies<TSectionId>) {
        this.#layout = dependencies.layout;
        this.#contextId = dependencies.contextId;
        this.#saveUnitId = dependencies.saveUnitId;
        this.#requestContextLabel = dependencies.requestContextLabel;
        this.#isCustomizationDisabled = dependencies.isCustomizationDisabled;
    }

    initialize(): void {
        if (this.#initialized) {
            this.sync();
            return;
        }
        this.#initialized = true;
        this.#layout.setChangeListener((): void => this.sync());
        this.#ensureSave().attach({
            resolveSaveButtons: (): readonly HTMLButtonElement[] => []
        });
        this.sync();
    }

    hasChanges(): boolean {
        return this.#layout.hasUnsavedChanges();
    }

    setEditing(editing: boolean): void {
        this.#editing = editing && this.#isEditAllowed() && this.#layout.isEditableLayoutMode();
        this.#syncLayoutLock();
    }

    sync(): void {
        if (!this.#initialized) {
            return;
        }
        if (!this.#isEditAllowed() || !this.#layout.isEditableLayoutMode()) {
            this.#editing = false;
        }
        this.#syncLayoutLock();
        this.#save?.notifyChanged();
        this.#edit?.sync();
    }

    destroy(): void {
        this.#editing = false;
        this.#layout.setChangeListener(null);
        this.#syncLayoutLock();
        this.#edit?.dispose();
        this.#save?.dispose();
        this.#edit = null;
        this.#save = null;
        this.#initialized = false;
    }

    #saveLayout(): void {
        const wasEditing = this.#editing;
        let saved = false;
        this.#editing = false;
        try {
            this.#layout.saveLayout();
            saved = true;
        } finally {
            if (!saved) {
                this.#editing = wasEditing && this.#isEditAllowed() && this.#layout.isEditableLayoutMode();
            }
            this.#syncLayoutLock();
            this.#edit?.sync();
        }
    }

    #ensureSave(): SaveController {
        if (this.#save) {
            return this.#save;
        }
        this.#save = createSaveController({
            headerContextId: this.#contextId,
            headerPriority: SAVE_HEADER_PRIORITY_PAGE,
            requestContextLabel: this.#requestContextLabel,
            units: [
                {
                    id: this.#saveUnitId,
                    hasChanges: (): boolean => this.hasChanges(),
                    save: (): void => this.#saveLayout()
                }
            ]
        });
        this.#edit = createHeaderEditController({
            contextId: this.#contextId,
            isAllowed: (): boolean => this.#isEditAllowed(),
            isCompactLayout: (): boolean => !this.#layout.isEditableLayoutMode(),
            isEditing: (): boolean => this.#editing,
            hasChanges: (): boolean => this.hasChanges(),
            setEditing: (editing: boolean): void => this.setEditing(editing)
        });
        return this.#save;
    }

    #isEditAllowed(): boolean {
        return !this.#isCustomizationDisabled();
    }

    #syncLayoutLock(): void {
        this.#layout.setLocked(!this.#editing);
    }
}

export { MovableLayoutEditController };
export type { MovableLayoutEditControllerDependencies };
