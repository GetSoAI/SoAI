/* SoAI - Content preview modal runtime actions [frontend/assets/ts/core/ui/modals/contentpreview/runtimeActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation, getWindowOpen } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { maybeConfirmExternalOpen } from '@core/ui/modals/contentpreview/externalOpen.ts';
import type { ContentPreviewTextController } from '@core/ui/modals/contentpreview/textController.ts';
import type { ContentPreviewImageNavigation, ContentPreviewImageNavigationDirection, ContentPreviewOpenRequest, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewRuntimeActionDependencies = Readonly<{
    getCurrentRequest: () => ContentPreviewOpenRequest | null;
    getCurrentTextRequest: () => ContentPreviewTextRequest | null;
    getCurrentImageNavigation: () => ContentPreviewImageNavigation | null;
    beginImageNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string) => void;
    cancelImageNavigation: () => void;
    requireModalRoot: () => HTMLElement;
    textController: ContentPreviewTextController;
}>;

type ContentPreviewRuntimeActions = Readonly<{
    handleDownload: () => Promise<void>;
    handleCopy: () => Promise<void>;
    handleAttach: () => Promise<void>;
    handleEnhance: () => Promise<void>;
    handleOpenSource: () => Promise<void>;
    handleImagePrevious: () => Promise<void>;
    handleImageNext: () => Promise<void>;
    resetImageNavigation: () => void;
}>;

const createContentPreviewRuntimeActions = (dependencies: ContentPreviewRuntimeActionDependencies): ContentPreviewRuntimeActions => {
    const windowOpen = getWindowOpen();
    const location = getLocation();

    const handleDownload = async (): Promise<void> => {
        const request = dependencies.getCurrentRequest();
        if (!request || !request.onRequestDownload) {
            return;
        }
        await request.onRequestDownload();
        showNotification(i18n.t('common.notifications.downloadStarted'), 'download');
    };

    const handleCopy = async (): Promise<void> => {
        const request = dependencies.getCurrentTextRequest();
        if (!request || !request.onRequestCopy) {
            return;
        }
        const modalRoot = dependencies.requireModalRoot();
        const draft = dependencies.textController.getDraftSnapshot(modalRoot);
        await request.onRequestCopy(draft ? draft.content : '');
    };

    const handleAttach = async (): Promise<void> => {
        const request = dependencies.getCurrentRequest();
        if (!request || !request.onRequestAttach) {
            return;
        }
        await request.onRequestAttach();
    };

    const handleEnhance = async (): Promise<void> => {
        const request = dependencies.getCurrentTextRequest();
        if (!request || !request.enhance) {
            return;
        }
        if (!request.enhance.isEnabledForBaseline(request.baseline)) {
            return;
        }
        await request.enhance.onRequestEnhance();
    };

    const handleOpenSource = async (): Promise<void> => {
        const request = dependencies.getCurrentRequest();
        if (!request || !request.openSourceUrl) {
            return;
        }
        const url = request.openSourceUrl;
        const confirmed = await maybeConfirmExternalOpen({ scope: request.scope, behavior: request.externalOpenBehavior, url });
        if (!confirmed) {
            return;
        }
        if (url.startsWith('#')) {
            location.assign(url);
            return;
        }
        windowOpen(url, '_blank', 'noopener,noreferrer');
    };

    let navigationPending = false;
    let queuedDirection: ContentPreviewImageNavigationDirection | null = null;
    let navigationSequence = 0;

    const resetImageNavigation = (): void => {
        navigationSequence += 1;
        navigationPending = false;
        queuedDirection = null;
    };

    const handleImageNavigation = async (direction: ContentPreviewImageNavigationDirection): Promise<void> => {
        if (!dependencies.getCurrentImageNavigation()) {
            return;
        }
        if (navigationPending) {
            queuedDirection = direction;
            return;
        }
        navigationPending = true;
        const sequence = navigationSequence;
        let nextDirection: ContentPreviewImageNavigationDirection | null = direction;
        try {
            while (nextDirection !== null && sequence === navigationSequence) {
                const navigation = dependencies.getCurrentImageNavigation();
                if (!navigation) {
                    break;
                }
                const previousRequest = dependencies.getCurrentRequest();
                dependencies.beginImageNavigation(nextDirection, nextDirection === 'previous' ? navigation.previousLoadingPath : navigation.nextLoadingPath);
                if (nextDirection === 'previous') {
                    await navigation.onRequestPrevious();
                } else {
                    await navigation.onRequestNext();
                }
                if (sequence !== navigationSequence) {
                    return;
                }
                if (previousRequest === dependencies.getCurrentRequest()) {
                    dependencies.cancelImageNavigation();
                    break;
                }
                nextDirection = queuedDirection;
                queuedDirection = null;
            }
        } catch (error) {
            if (sequence === navigationSequence) {
                dependencies.cancelImageNavigation();
                throw error;
            }
        } finally {
            if (sequence === navigationSequence) {
                navigationPending = false;
                queuedDirection = null;
            }
        }
    };

    const handleImagePrevious = async (): Promise<void> => await handleImageNavigation('previous');

    const handleImageNext = async (): Promise<void> => await handleImageNavigation('next');

    return Object.freeze({
        handleDownload,
        handleCopy,
        handleAttach,
        handleEnhance,
        handleOpenSource,
        handleImagePrevious,
        handleImageNext,
        resetImageNavigation
    });
};

export { createContentPreviewRuntimeActions };
