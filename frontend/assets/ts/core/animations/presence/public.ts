/* SoAI - Presence motion public surface [frontend/assets/ts/core/animations/presence/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { insertWithPresence, removeWithPresence, resolveNextPresenceAnchor } from '@core/animations/presence/presenceDom.ts';
export { reconcilePresenceList } from '@core/animations/presence/presenceList.ts';
export type { PresenceListReconcileArguments } from '@core/animations/presence/presenceList.ts';
export { createPresenceRuntime } from '@core/animations/presence/presenceRuntime.ts';
export type { PresenceRuntimeService } from '@core/animations/presence/presenceRuntime.ts';
export { PRESENCE_EXITING_SELECTOR, exitWithPresence, isPresenceExiting, prepareEnterWithPresence, requestPresenceEnter } from '@core/animations/presence/presenceTransitions.ts';
export { animatePresenceExit, animatePresenceMorph, deferUntilPresenceExitsSettle, finishPresenceAnimations, hasPresenceAnimationInSubtree, isPresenceAnimating, isPresenceMorphing, measurePresenceSize, stopPresenceAnimation } from '@core/animations/presence/presenceMotion.ts';
export type { PresenceSize } from '@core/animations/presence/presenceMotion.ts';
