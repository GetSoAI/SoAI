/* SoAI - Captured page and document presentation ownership [frontend/assets/ts/core/presentationOwner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GlobalPresentationOwner, PresentationOwner } from '@core/routing/router/types.ts';

const createGlobalPresentationOwner = (ownerId: string): GlobalPresentationOwner => {
    const normalized = ownerId.trim();
    if (!normalized) throw new Error('Global presentation requires an owner identifier');
    return Object.freeze({ type: 'global', ownerId: normalized, generation: Symbol(normalized) });
};

const isPresentationOwnerCurrent = (owner: PresentationOwner): boolean => owner.type === 'global' || owner.admission.isCurrent();
const isPresentationOwnerActive = (owner: PresentationOwner): boolean => owner.type === 'global' || owner.admission.isActive();
const isPresentationOwnerMutationAllowed = (owner: PresentationOwner): boolean => owner.type === 'global' || owner.admission.canMutate();
const isPresentationOwnerFocused = (owner: PresentationOwner): boolean => owner.type === 'global' || owner.presentation.isFocused();
const requirePresentationOwnerActive = (owner: PresentationOwner): void => {
    if (owner.type !== 'global') owner.admission.requireActive();
};

export { createGlobalPresentationOwner, isPresentationOwnerActive, isPresentationOwnerCurrent, isPresentationOwnerFocused, isPresentationOwnerMutationAllowed, requirePresentationOwnerActive };
