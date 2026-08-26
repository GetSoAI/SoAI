/* SoAI - Automation run route redirect middleware [frontend/assets/ts/app/bootstrap/navigation/automationRunRedirect.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { navigationResult } from '@core/navigationMiddleware.ts';
import type { RouterMiddleware } from '@core/routing/router/guards.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';
import { isString } from '@core/typeGuards.ts';
import { buildChatConversationRoute, normalizeConversationId } from '@features/chat/public.ts';
import type { AutomationDataService } from '@features/automation/public.ts';

const AUTOMATION_PAGE_COMPONENT = 'automation';

const readAutomationRunId = (context: NavigationContext): string | null => {
    if (context.route.component !== AUTOMATION_PAGE_COMPONENT) {
        return null;
    }
    const runId = context.parameters['run_id'];
    return isString(runId) && runId.trim() ? runId.trim() : null;
};

const createAutomationRunConversationRedirectMiddleware = (dataService: AutomationDataService): RouterMiddleware => {
    return async (context, next) => {
        const runId = readAutomationRunId(context);
        if (!runId) {
            return next();
        }
        try {
            const run = await dataService.getRun(runId);
            const conversationId = normalizeConversationId(run.convId);
            if (!conversationId) {
                return next();
            }
            return navigationResult.redirect(buildChatConversationRoute(conversationId), { replace: true });
        } catch (error) {
            errorHandler.warn('AutomationRunRedirect', 'Failed to resolve automation run conversation route', ensureError(error));
            return next();
        }
    };
};

export { createAutomationRunConversationRedirectMiddleware };
