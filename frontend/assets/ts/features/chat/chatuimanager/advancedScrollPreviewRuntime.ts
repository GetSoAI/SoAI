/* SoAI - Advanced scroll preview observer and rendering runtime [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { ADVANCED_SCROLL_HIDDEN_CLASS } from '@features/chat/chatuimanager/advancedScrollPreviewConstants.ts';
import { createAdvancedScrollPreviewBottomOffsetController } from '@features/chat/chatuimanager/advancedScrollPreviewBottomOffset.ts';
import { createAdvancedScrollPreviewDragRuntime } from '@features/chat/chatuimanager/advancedScrollPreviewDragRuntime.ts';
import { createAdvancedScrollPreviewDomMinimapRuntime, type AdvancedScrollPreviewDomMinimapMeasurement } from '@features/chat/chatuimanager/advancedScrollPreviewDomMinimap.ts';
import { computeAdvancedScrollPreviewLayoutMetrics, computeAdvancedScrollPreviewThumbRect, type LayoutMetrics, type ThumbRect } from '@features/chat/chatuimanager/advancedScrollPreviewLayout.ts';
import { applyAdvancedScrollPreviewThumbStyles, resetAdvancedScrollPreviewStyles } from '@features/chat/chatuimanager/advancedScrollPreviewStyles.ts';
import { createAdvancedScrollPreviewVisibilityController } from '@features/chat/chatuimanager/advancedScrollPreviewVisibility.ts';
import type { AdvancedScrollPreviewElements, ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type PreviewFrameMeasurement = {
    bottomOffsetPx: number | null;
    layout: LayoutMetrics;
    minimap: AdvancedScrollPreviewDomMinimapMeasurement | null;
    thumb: ThumbRect | null;
    updateContent: boolean;
};

const STREAMING_DRAW_DEBOUNCE_MS = 48;
const IDLE_DRAW_DEBOUNCE_MS = 120;
const PREVIEW_FRAME_KEY = 'advanced-scroll-preview';

export const createAdvancedScrollPreviewRuntime = (context: ChatUIManagerContext, elements: AdvancedScrollPreviewElements): (() => void) | null => {
    const { messagesArea, messagesRoot, overlay, canvas, viewport, fadeTop, fadeBottom } = elements;
    const doc = context.dependencies.dom.getDocument();
    const win = doc.defaultView;
    if (!win || typeof win.ResizeObserver !== 'function' || typeof win.MutationObserver !== 'function') {
        return null;
    }
    const coordinator = acquireMainTimelineCoordinator(messagesArea, messagesRoot);
    const shell = overlay.parentElement instanceof HTMLElement ? overlay.parentElement : null;
    const inputWrapperCandidate = context.dependencies.optionalUI('.chat-input-wrapper');
    const inputWrapper = inputWrapperCandidate instanceof HTMLElement ? inputWrapperCandidate : null;
    const inputActionsCandidate = context.dependencies.optionalUI('.chat-input-actions');
    const inputActions = inputActionsCandidate instanceof HTMLElement ? inputActionsCandidate : null;
    let stopDrag: (() => void) | null = null;
    let isPreviewDragging = false;
    let isDisposed = false;
    let hasEverBeenScrollable = false;
    let geometryPending = false;
    let contentPending = false;
    let contentPendingAfterTouch = false;
    let thumbPending = false;
    let lastLayout: LayoutMetrics | null = null;

    const isCurrentConversationStreaming = (): boolean => {
        const conversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
        return conversationId ? context.dependencies.session.isConversationExecuting(conversationId) : false;
    };

    const minimap = createAdvancedScrollPreviewDomMinimapRuntime({
        coordinator,
        doc,
        messagesArea,
        messagesRoot,
        overlay,
        host: canvas
    });

    const computeLayoutMetrics = (): LayoutMetrics => {
        const isWidescreen = messagesArea.classList.contains('widescreen-mode');
        const isScrollableNow = messagesArea.scrollHeight > messagesArea.clientHeight + 1;
        if (isScrollableNow) {
            hasEverBeenScrollable = true;
        }
        return computeAdvancedScrollPreviewLayoutMetrics({
            grooveHeight: overlay.clientHeight,
            scrollHeight: messagesArea.scrollHeight,
            clientHeight: messagesArea.clientHeight,
            isWidescreen,
            isNarrowViewport: measureLayoutViewport(messagesArea).width <= 1200,
            hasEverBeenScrollable
        });
    };

    const isRuntimeConnected = (): boolean => !isDisposed && messagesArea.isConnected && messagesRoot.isConnected && overlay.isConnected && canvas.isConnected && viewport.isConnected && fadeTop.isConnected && fadeBottom.isConnected;

    const visibility = createAdvancedScrollPreviewVisibilityController({
        context,
        overlay,
        isInteractionActive: () => isPreviewDragging,
        onHide: () => {
            stopDrag?.();
            context.dependencies.toggleClassName(overlay, CSS_CLASSES.HOVER, false);
        },
        onResume: () => scheduleGeometrySync()
    });
    const bottomOffset = createAdvancedScrollPreviewBottomOffsetController({ context, win, overlay, shell, inputWrapper, inputActions });

    const applyPreviewFrame = (measurement: PreviewFrameMeasurement): void => {
        if (!isRuntimeConnected()) {
            return;
        }
        if (measurement.bottomOffsetPx !== null) {
            bottomOffset.apply(measurement.bottomOffsetPx);
        }
        if (measurement.updateContent) {
            if (!measurement.layout.visibleWanted) {
                visibility.sync(false);
                return;
            }
            if (measurement.minimap) {
                const hasPending = minimap.apply(measurement.minimap);
                if (hasPending) {
                    contentPending = true;
                    schedulePreviewFrame();
                }
            }
            visibility.sync(minimap.hasVisibleContent());
        }
        if (visibility.isVisible() && measurement.thumb) {
            applyAdvancedScrollPreviewThumbStyles(context, { viewport, fadeTop, fadeBottom }, measurement.layout, measurement.thumb);
        }
    };

    const measurePreviewFrame = (): (() => void) | null => {
        if (!isRuntimeConnected()) {
            return null;
        }
        const updateGeometry = geometryPending;
        let updateContent = contentPending;
        const updateThumb = thumbPending;
        geometryPending = false;
        contentPending = false;
        thumbPending = false;
        if (updateContent && coordinator.isDirectTouchActive()) {
            updateContent = false;
            contentPendingAfterTouch = true;
        }
        const layout = updateGeometry || updateContent ? computeLayoutMetrics() : lastLayout;
        if (!layout) {
            return null;
        }
        lastLayout = layout;
        const measurement: PreviewFrameMeasurement = {
            bottomOffsetPx: updateGeometry ? bottomOffset.measure() : null,
            layout,
            minimap: updateContent ? minimap.measure() : null,
            thumb: updateContent || updateThumb ? computeAdvancedScrollPreviewThumbRect(layout, messagesArea.scrollTop) : null,
            updateContent
        };
        return () => applyPreviewFrame(measurement);
    };

    function schedulePreviewFrame(): void {
        if (!isDisposed) {
            coordinator.scheduleFrame(PREVIEW_FRAME_KEY, measurePreviewFrame);
        }
    }

    const scheduleContentNow = (): void => {
        if (isDisposed) {
            return;
        }
        if (coordinator.isDirectTouchActive()) {
            contentPendingAfterTouch = true;
            return;
        }
        contentPending = true;
        schedulePreviewFrame();
    };
    const scheduleStreamingDraw = context.dependencies.runtime.createDebouncedHandler(scheduleContentNow, STREAMING_DRAW_DEBOUNCE_MS);
    const scheduleIdleDraw = context.dependencies.runtime.createDebouncedHandler(scheduleContentNow, IDLE_DRAW_DEBOUNCE_MS);
    const scheduleDraw = (): void => {
        if (isDisposed) {
            return;
        }
        if (coordinator.isDirectTouchActive()) {
            contentPendingAfterTouch = true;
            return;
        }
        if (isCurrentConversationStreaming()) {
            scheduleIdleDraw.cancel?.();
            scheduleStreamingDraw();
            return;
        }
        scheduleStreamingDraw.cancel?.();
        scheduleIdleDraw();
    };
    const scheduleGeometrySync = (): void => {
        if (isDisposed) {
            return;
        }
        geometryPending = true;
        schedulePreviewFrame();
        scheduleDraw();
    };
    const scheduleThumbUpdate = (): void => {
        thumbPending = true;
        schedulePreviewFrame();
    };

    const resizeDisposer = coordinator.subscribeResize((entries) => {
        minimap.markDirtyFromResize(entries);
        for (const entry of entries) {
            if (entry.target === overlay || entry.target === messagesArea || entry.target === inputActions || entry.target === inputWrapper) {
                scheduleGeometrySync();
                return;
            }
        }
        scheduleContentNow();
    });
    const observedResizeDisposers = [coordinator.observeResize(messagesArea), coordinator.observeResize(overlay), coordinator.observeResize(messagesRoot)];
    if (inputActions) {
        observedResizeDisposers.push(coordinator.observeResize(inputActions));
    }
    if (inputWrapper) {
        observedResizeDisposers.push(coordinator.observeResize(inputWrapper));
    }
    const mutationDisposer = coordinator.subscribeMutations((mutations) => {
        if (isDisposed) {
            return;
        }
        const messageMutations = mutations.filter((mutation) => mutation.target !== messagesArea);
        if (minimap.markDirtyFromMutations(messageMutations)) {
            if (visibility.isVisible()) {
                scheduleDraw();
            } else {
                scheduleContentNow();
            }
        }
        if (mutations.some((mutation) => mutation.target === messagesArea)) {
            scheduleGeometrySync();
        }
    });
    const touchSettledDisposer = coordinator.subscribeTouchSettled(() => {
        if (!contentPendingAfterTouch || isDisposed) {
            return;
        }
        contentPendingAfterTouch = false;
        scheduleContentNow();
    });
    const onScrollDisposer = context.dependencies.runtime.on(messagesArea, 'scroll', scheduleThumbUpdate, { passive: true });
    const onWindowResizeDisposer = context.dependencies.runtime.on(win, 'resize', scheduleGeometrySync);
    const onScaleDisposer = context.dependencies.runtime.on(win, INTERFACE_SCALE_CHANGED_EVENT, scheduleGeometrySync);
    const dragRuntime = createAdvancedScrollPreviewDragRuntime({
        context,
        overlay,
        messagesArea,
        getVisibilityState: () => {
            if (!isRuntimeConnected()) {
                return null;
            }
            const current = computeLayoutMetrics();
            lastLayout = current;
            const thumb = computeAdvancedScrollPreviewThumbRect(current, messagesArea.scrollTop);
            return {
                visible: visibility.isVisible() && current.maxScrollTop > 0,
                grooveHeight: current.grooveHeight,
                thumbTop: thumb.thumbTop,
                thumbHeight: thumb.thumbHeight,
                maxScrollTop: current.maxScrollTop,
                scrollHeight: current.scrollHeight,
                clientHeight: current.clientHeight
            };
        },
        scheduleThumbUpdate,
        onDragStateChange: (active) => {
            isPreviewDragging = active;
            if (!active) {
                scheduleGeometrySync();
            }
        }
    });
    stopDrag = dragRuntime.stop;
    context.state.advancedScrollPreviewVisibilityController = visibility;
    scheduleGeometrySync();

    return () => {
        isDisposed = true;
        onWindowResizeDisposer();
        onScaleDisposer();
        onScrollDisposer();
        dragRuntime.dispose();
        scheduleStreamingDraw.cancel?.();
        scheduleIdleDraw.cancel?.();
        visibility.dispose();
        context.state.advancedScrollPreviewVisibilityController = null;
        touchSettledDisposer();
        mutationDisposer();
        for (const resizeObservationDisposer of observedResizeDisposers) {
            resizeObservationDisposer();
        }
        resizeDisposer();
        minimap.dispose();
        coordinator.cancelFrame(PREVIEW_FRAME_KEY);
        coordinator.release();
        context.dependencies.toggleClassName(overlay, ADVANCED_SCROLL_HIDDEN_CLASS, true);
        resetAdvancedScrollPreviewStyles(context, { overlay, viewport, fadeTop, fadeBottom });
    };
};
