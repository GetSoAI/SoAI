/* SoAI - Shared UI toast notification pointer events [frontend/assets/ts/core/ui/notifications/toastNotificationPointerEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isSupportedNotificationPointerStart = (event: PointerEvent): boolean => {
    if (!event.isPrimary) {
        return false;
    }
    if (event.pointerType === 'touch') {
        return false;
    }
    if (event.pointerType !== 'mouse') {
        return true;
    }
    return event.button === 0;
};

const isNotificationPointerEventForGesture = (event: PointerEvent, source: 'pointer' | 'touch', pointerId: number): boolean => {
    if (source === 'pointer') {
        return event.pointerId === pointerId;
    }
    return event.isPrimary;
};

export { isNotificationPointerEventForGesture, isSupportedNotificationPointerStart };
