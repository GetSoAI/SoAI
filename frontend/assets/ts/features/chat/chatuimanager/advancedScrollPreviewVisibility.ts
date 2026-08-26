/* SoAI - Chat feature UI manager advanced scroll preview visibility [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AdvancedScrollPreviewVisibilityController, ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { ADVANCED_SCROLL_HIDDEN_CLASS, VISIBILITY_HIDE_DELAY_MS } from '@features/chat/chatuimanager/advancedScrollPreviewConstants.ts';

export const createAdvancedScrollPreviewVisibilityController = (input: { context: ChatUIManagerContext; overlay: HTMLElement; isInteractionActive: () => boolean; onHide: () => void; onResume: () => void }): AdvancedScrollPreviewVisibilityController => {
    let lastVisibility: boolean | null = null;
    let visibilityWanted = false;
    let hideTimerId: number | null = null;
    let suspended = false;

    const cancelHideTimer = (): void => {
        if (hideTimerId === null) {
            return;
        }
        input.context.dependencies.runtime.clearTimer(hideTimerId);
        hideTimerId = null;
    };

    const commitHidden = (): void => {
        cancelHideTimer();
        if (lastVisibility === false) {
            return;
        }
        lastVisibility = false;
        input.context.dependencies.toggleClassName(input.overlay, ADVANCED_SCROLL_HIDDEN_CLASS, true);
        input.onHide();
    };

    const commitVisible = (): void => {
        cancelHideTimer();
        if (lastVisibility === true) {
            return;
        }
        lastVisibility = true;
        input.context.dependencies.toggleClassName(input.overlay, ADVANCED_SCROLL_HIDDEN_CLASS, false);
    };

    const sync = (visibleWanted: boolean): void => {
        if (suspended) {
            return;
        }
        visibilityWanted = visibleWanted;
        if (lastVisibility === null) {
            if (visibleWanted) {
                commitVisible();
            } else {
                lastVisibility = false;
                input.context.dependencies.toggleClassName(input.overlay, ADVANCED_SCROLL_HIDDEN_CLASS, true);
                input.onHide();
            }
            return;
        }

        if (visibleWanted) {
            commitVisible();
            return;
        }

        if (input.isInteractionActive()) {
            cancelHideTimer();
            return;
        }

        if (hideTimerId !== null) {
            return;
        }

        hideTimerId = input.context.dependencies.runtime.setTimer(() => {
            hideTimerId = null;
            if (!visibilityWanted && !input.isInteractionActive()) {
                commitHidden();
            }
        }, VISIBILITY_HIDE_DELAY_MS);
    };

    const suspend = (): void => {
        suspended = true;
        visibilityWanted = false;
        commitHidden();
    };

    const resume = (): void => {
        if (!suspended) {
            return;
        }
        suspended = false;
        input.onResume();
    };

    const dispose = (): void => {
        cancelHideTimer();
    };

    return {
        sync,
        suspend,
        resume,
        isVisible: () => lastVisibility === true,
        dispose
    };
};
