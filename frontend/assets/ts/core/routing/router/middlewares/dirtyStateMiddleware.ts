/* SoAI - Shared routing dirty state middleware [frontend/assets/ts/core/routing/router/middlewares/dirtyStateMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { NAVIGATION_STATUS, navigationResult } from '@core/navigationMiddleware.ts';
import type { NavigationResultType, NavigationProtectionApproval, NavigationContext, NavigationPlacementAdmission } from '@core/routing/router/types.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import { evaluateDirtyStateGuardBatch } from '@core/navigationGuards.ts';

import { normalizeMiddlewareOutcome } from '@core/routing/router/navigationMiddlewareNormalization.ts';

import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const evaluatePlacementDestruction = (placement: NavigationPlacementAdmission): Promise<NavigationResultType | null> => (placement.evaluateGuards ? placement.evaluateGuards() : evaluateDirtyStateGuardBatch(placement.guardContexts));

const validatePlacementDestruction = (placement: NavigationPlacementAdmission, approvals: readonly NavigationProtectionApproval[], signal: AbortSignal): void => {
    throwIfAborted(signal);
    if (approvals.length !== placement.guardContexts.length || !approvals.every((approval) => approval.isCurrent())) throw createAbortError('Navigation protection changed during page preparation');
};

const admitPlacementDestruction = (placement: NavigationPlacementAdmission, approvals: readonly NavigationProtectionApproval[], signal: AbortSignal): void => {
    validatePlacementDestruction(placement, approvals, signal);
    placement.finalAdmission?.();
};

const commitPlacementClose = async (placement: NavigationPlacementAdmission, approvals: readonly NavigationProtectionApproval[], signal: AbortSignal, publish: () => void): Promise<void> => {
    if (!placement.close) throw new Error('Pane closing requires its native resource release');
    admitPlacementDestruction(placement, approvals, signal);
    const release = await placement.prepareClose?.();
    try {
        validatePlacementDestruction(placement, approvals, signal);
        await placement.close(publish);
    } finally {
        release?.();
    }
};

const createDirtyStateNavigationMiddleware = (): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const downstream = await next();
        throwIfAborted(context.signal);
        if (downstream.status !== NAVIGATION_STATUS.CONTINUE) return downstream;
        let placement: NavigationPlacementAdmission;
        try {
            placement = await context.admitPlacement(context);
        } catch (error) {
            throwIfAborted(context.signal);
            if (error instanceof PagePaneUnavailableError) return navigationResult.block(error.code, error);
            throw error;
        }
        throwIfAborted(context.signal);
        if (placement.guardPhase === 'before-commit') return downstream;
        const verdict = await evaluatePlacementDestruction(placement);
        throwIfAborted(context.signal);
        if (verdict !== null) return normalizeMiddlewareOutcome(verdict);
        return downstream;
    };
};

export { createDirtyStateNavigationMiddleware, evaluatePlacementDestruction, admitPlacementDestruction, commitPlacementClose };
