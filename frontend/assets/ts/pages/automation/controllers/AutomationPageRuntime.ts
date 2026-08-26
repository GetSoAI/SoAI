/* SoAI - Automation page platform ownership to domain operation mapping [frontend/assets/ts/pages/automation/controllers/AutomationPageRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildChatConversationRoute } from '@features/chat/public.ts';
import type { ControllerDependencies, ControllerRuntimeDependencies } from '@pages/automation/controllers/contracts.ts';

const createAutomationPageEnvironment = (dependencies: ControllerDependencies): ControllerRuntimeDependencies => ({
    ...dependencies,
    requireHTMLElement: (selector, context) => dependencies.pageDom.requireHTMLElement(selector, context instanceof Element ? context : undefined),
    replaceElementContent: (element, content, options) => dependencies.pageDom.replaceContent(element, content, options),
    flushDOMUpdates: () => dependencies.pageDom.flush(),
    getIconSync: (icon, options) => dependencies.services.getIconSync(icon, options),
    showNotification: (message, type, duration) => dependencies.feedback.show(message, type, duration),
    navigateToConversation: (conversationId) => dependencies.router.navigate(buildChatConversationRoute(conversationId)),
    getStyleProp: (property, element) => dependencies.services.getStyleProperty(property, element),
    requestAnimationFrame: (callback) => {
        const tracker = dependencies.pageResources.tracker;
        if (!tracker) throw new Error('Automation page resources are not available');
        return tracker.requestAnimationFrame(callback);
    },
    setTimeout: (callback, delay) => dependencies.pageResources.setTimeout(callback, delay),
    clearTimer: (timerId) => dependencies.pageResources.clearTimer(timerId),
    runWithBoundary: (operation, task) => dependencies.pageLifecycle.run(operation, task)
});

export { createAutomationPageEnvironment };
