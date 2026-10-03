/* SoAI - Presence motion public surface [frontend/assets/ts/core/animations/presence/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { insertWithPresence, removeWithPresence, resolveNextPresenceAnchor } from '@core/animations/presence/presenceDom.ts';
export { createPresenceRuntime } from '@core/animations/presence/presenceRuntime.ts';
export type { PresenceRuntimeService } from '@core/animations/presence/presenceRuntime.ts';
export { PRESENCE_EXITING_SELECTOR, isPresenceExiting, requestPresenceEnter } from '@core/animations/presence/presenceTransitions.ts';
export { finishPresenceAnimations, isPresenceAnimating } from '@core/animations/presence/presenceMotion.ts';
