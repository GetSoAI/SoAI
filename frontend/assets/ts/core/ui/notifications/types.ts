/* SoAI - Shared UI notifications contracts [frontend/assets/ts/core/ui/notifications/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type NotificationType = 'success' | 'error' | 'warning' | 'danger' | 'info' | 'copy' | 'refresh' | 'download';

interface NotificationOptions {
    message?: string;
    type?: NotificationType;
    buttons?: NotificationButton[];
    dedupeKey?: string;
    icon?: string;
    onClose?: () => void;
}

interface NotificationButton {
    text: string;
    icon?: string;
    variant?: string;
    action?: () => Promise<boolean | void> | boolean | void;
}

type NotificationPreferences = Readonly<{
    getNotificationDuration: () => number;
}>;

interface NotificationStoragePreferences {
    getNotificationDuration: () => JsonValue;
}

interface NotificationUserOptions {
    duration?: number;
    showNotification?: boolean;
}

interface NotificationInteractionLifecycle {
    dismiss: () => void;
    pauseAutoDismiss: () => void;
    resumeAutoDismiss: () => void;
}

interface NotificationTimerControls {
    clear: () => void;
    pause: () => void;
    resume: () => void;
}

interface ToastNotificationGestureStart {
    source: 'pointer' | 'touch';
    pointerId: number;
    touchIdentifier: number | null;
    pointerType: string;
    clientX: number;
    clientY: number;
}

interface ToastNotificationGestureState {
    source: 'pointer' | 'touch';
    pointerId: number;
    touchIdentifier: number | null;
    pointerType: string;
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
    dragging: boolean;
}

interface ToastNotificationSwipeOptions {
    notification: HTMLElement;
    lifecycle: NotificationInteractionLifecycle;
    isExpanded: () => boolean;
    isBlockedTarget: (target: EventTarget | null) => boolean;
    suppressUpcomingClick: () => void;
}

export type { NotificationButton, NotificationInteractionLifecycle, NotificationOptions, NotificationPreferences, NotificationStoragePreferences, NotificationTimerControls, NotificationType, NotificationUserOptions, ToastNotificationGestureStart, ToastNotificationGestureState, ToastNotificationSwipeOptions };
