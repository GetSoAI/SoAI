/* SoAI - Overlays feature public surface [frontend/assets/ts/features/overlays/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { CountdownOverlay, COUNTDOWN_OVERLAY_SERVICE_ID } from '@features/overlays/Countdown.ts';
export { POWER_ACTION_OVERLAY_SERVICE_ID } from '@features/overlays/PowerAction.ts';
export { RESTART_OVERLAY_SERVICE_ID } from '@features/overlays/restart/constants.ts';
export { isOperationType } from '@features/overlays/restart/guards.ts';
export type { OperationType, RestartOverlayShowOptions } from '@features/overlays/restart/types.ts';
