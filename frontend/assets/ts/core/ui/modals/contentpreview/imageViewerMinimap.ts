/* SoAI - Content preview image viewer minimap [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerMinimap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';

type MountArguments = Readonly<{
    refs: ContentPreviewImageViewerRefs;
    resources: ResourceTracker;
}>;

type ContentPreviewImageViewerMinimap = Readonly<{
    isVisible: () => boolean;
    setVisible: (visible: boolean) => void;
    scheduleHide: (delayMs: number) => void;
    dispose: () => void;
}>;

const createContentPreviewImageViewerMinimap = ({ refs, resources }: MountArguments): ContentPreviewImageViewerMinimap => {
    let visible = false;
    let hideTimer: number | null = null;

    const clearHideTimer = (): void => {
        if (hideTimer === null) {
            return;
        }
        resources.clearTimeout(hideTimer);
        hideTimer = null;
    };

    const setVisible = (nextVisible: boolean): void => {
        visible = nextVisible;
        refs.minimap.classList.toggle('is-active', nextVisible);
        refs.minimap.setAttribute('aria-hidden', nextVisible ? 'false' : 'true');
    };

    const scheduleHide = (delayMs: number): void => {
        clearHideTimer();
        hideTimer = resources.setTimeout(() => {
            hideTimer = null;
            setVisible(false);
        }, delayMs);
    };

    return Object.freeze({
        isVisible: (): boolean => visible,
        setVisible,
        scheduleHide,
        dispose: (): void => {
            clearHideTimer();
            setVisible(false);
        }
    });
};

export { createContentPreviewImageViewerMinimap };
export type { ContentPreviewImageViewerMinimap };
