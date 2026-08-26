/* SoAI - Shared header editing controller [frontend/assets/ts/core/headeredit/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { isFunction, isString } from '@core/typeGuards.ts';

interface HeaderEditControllerOptions {
    contextId: string;
    isAllowed: () => boolean;
    isCompactLayout: () => boolean;
    isEditing: () => boolean;
    hasChanges: () => boolean;
    setEditing: (editing: boolean) => void;
}

interface HeaderEditController {
    sync: () => void;
    dispose: () => void;
}

const HEADER_EDIT_PRIORITY_PAGE = 100;

const ensureHeaderEditOptions = (options: HeaderEditControllerOptions): void => {
    if (!isString(options.contextId) || !options.contextId.trim()) {
        throw new Error('Header edit controller requires a non-empty contextId');
    }
    const hasRequiredCallbacks = isFunction(options.isAllowed) && isFunction(options.isCompactLayout) && isFunction(options.isEditing) && isFunction(options.hasChanges) && isFunction(options.setEditing);
    if (!hasRequiredCallbacks) {
        throw new Error('Header edit controller requires state callbacks');
    }
};

const createHeaderEditController = (options: HeaderEditControllerOptions): HeaderEditController => {
    ensureHeaderEditOptions(options);
    const headerAction: HeaderActionController = createHeaderActionController({
        actionId: 'edit',
        contextId: options.contextId
    });
    let disposed = false;

    const handleClick = (): void => {
        if (disposed) {
            return;
        }
        options.setEditing(!options.isEditing());
        sync();
    };

    const sync = (): void => {
        if (disposed) {
            return;
        }
        const allowed = options.isAllowed();
        const compact = options.isCompactLayout();
        if ((!allowed || compact) && options.isEditing()) {
            options.setEditing(false);
        }
        getHeaderActions().setLayoutEditActive(options.contextId, options.isEditing());
        if (!allowed || compact || options.hasChanges()) {
            headerAction.hide();
            return;
        }
        const editing = options.isEditing();
        headerAction.show({
            priority: HEADER_EDIT_PRIORITY_PAGE,
            className: editing ? 'header-action--edit ui-variant-accent is-active' : 'header-action--edit ui-variant-neutral',
            pressed: editing,
            onClick: handleClick
        });
    };

    return {
        sync,
        dispose(): void {
            if (disposed) {
                return;
            }
            disposed = true;
            getHeaderActions().setLayoutEditActive(options.contextId, false);
            headerAction.dispose();
        }
    };
};

export { createHeaderEditController };
export type { HeaderEditController };
