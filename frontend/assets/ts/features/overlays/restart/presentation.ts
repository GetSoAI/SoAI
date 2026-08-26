/* SoAI - Restart overlay presentation [frontend/assets/ts/features/overlays/restart/presentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { RESTART_STATUS_ICON_HIDDEN_CLASS, getRestartContent } from '@features/overlays/restart/constants.ts';
import { setRestartOverlayVisibility } from '@features/overlays/restart/effects.ts';
import type { OperationType, OverlayElements } from '@features/overlays/restart/types.ts';

interface RestartPresentationOperations {
    addClassName: (element: HTMLElement, className: string) => void;
    removeClassName: (element: HTMLElement, className: string) => void;
    updateHtml: (element: HTMLElement, value: string | TrustedHtml) => void;
    updateText: (element: HTMLElement, value: string) => void;
}

const showRestartPresentation = (elements: OverlayElements, type: OperationType, operations: RestartPresentationOperations): boolean => {
    const { overlay, message, description, statusIcon } = elements;
    if (!overlay) return false;
    const content = getRestartContent(type);
    if (message) operations.updateText(message, content.message);
    if (description) operations.updateText(description, content.description);
    if (statusIcon) operations.updateHtml(statusIcon, getIconSync(content.statusIcon, { size: 68, strokeWidth: 1.5 }));
    operations.removeClassName(overlay, RESTART_STATUS_ICON_HIDDEN_CLASS);
    setRestartOverlayVisibility({ elements, addClassName: operations.addClassName, removeClassName: operations.removeClassName, setHidden: false });
    return true;
};

const hideRestartPresentation = (elements: OverlayElements, operations: Pick<RestartPresentationOperations, 'addClassName' | 'removeClassName'>): void => {
    setRestartOverlayVisibility({ elements, addClassName: operations.addClassName, removeClassName: operations.removeClassName, setHidden: true });
    if (elements.overlay) operations.removeClassName(elements.overlay, RESTART_STATUS_ICON_HIDDEN_CLASS);
};

export { hideRestartPresentation, showRestartPresentation };
