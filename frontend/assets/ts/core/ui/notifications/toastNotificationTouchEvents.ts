/* SoAI - Shared UI toast notification touch events [frontend/assets/ts/core/ui/notifications/toastNotificationTouchEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const findTouchByIdentifier = (touches: TouchList, identifier: number): Touch | null => {
    for (let index = 0; index < touches.length; index += 1) {
        const touch = touches.item(index);
        if (touch?.identifier === identifier) {
            return touch;
        }
    }
    return null;
};

const preventCancelableEventDefault = (event: Event): void => {
    if (event.cancelable) {
        event.preventDefault();
    }
};

export { findTouchByIdentifier, preventCancelableEventDefault };
