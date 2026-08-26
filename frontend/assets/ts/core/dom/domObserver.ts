/* SoAI - Shared DOM observer [frontend/assets/ts/core/dom/domObserver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDomDocument, getDomWindow } from '@core/dom/domEnvironment.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFiniteNumber, isNode } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ObserveMutationsOptions {
    root?: Node;
    timeout?: number;
    rejectionMessage?: string;
    includeAttributes?: boolean;
}

const observeMutationsUntil = <T>(evaluator: () => T | null | undefined | false, { root = getDomDocument(), timeout = 0, rejectionMessage = 'Timeout waiting for condition', includeAttributes = false }: ObserveMutationsOptions = {}): Promise<T> => {
    return new Promise((resolvePromise, rejectPromise) => {
        const target = root;
        let timerId: number | null = null;
        let active = true;

        const finalize = (callback: () => void): void => {
            active = false;
            observer.disconnect();
            if (timerId) {
                clearTimeout(timerId);
            }
            callback();
        };

        const observer = new MutationObserver(() => {
            if (!active) return;
            let result: T | null | undefined | false;
            try {
                result = evaluator();
            } catch (error) {
                finalize(() => rejectPromise(error));
                throw ensureError(error);
            }
            if (result === null || result === undefined || result === false) return;
            finalize(() => resolvePromise(result));
        });

        observer.observe(target, {
            childList: true,
            subtree: true,
            attributes: includeAttributes
        });

        if (isFiniteNumber(timeout) && timeout > 0) {
            timerId = getDomWindow().setTimeout(() => {
                finalize(() => rejectPromise(new Error(rejectionMessage)));
            }, timeout);
        }
    });
};

class DomObserver {
    static async waitForElement(selector: string, parent?: Element | Document | null, timeout = 5000): Promise<Element> {
        try {
            const doc = getDomDocument();
            const searchRoot = parent ?? doc.body;
            const evaluator = (): Element | null => searchRoot?.querySelector?.(selector) ?? null;
            const observationRoot = isNode(searchRoot) ? searchRoot : doc.body;
            return await observeMutationsUntil(evaluator, {
                root: observationRoot,
                timeout,
                rejectionMessage: `Timeout waiting for element: ${selector}`
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DomObserver', `Failed to wait for element ${selector}`, runtimeError);
            throw runtimeError;
        }
    }

    static async waitForCondition(conditionFunctionValue: () => boolean, timeout = 5000): Promise<void> {
        try {
            await observeMutationsUntil(conditionFunctionValue, {
                timeout,
                includeAttributes: true,
                rejectionMessage: 'Timeout waiting for condition'
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DomObserver', 'Failed to wait for condition', runtimeError);
            throw runtimeError;
        }
    }

    static async animationFrame(): Promise<DOMHighResTimeStamp> {
        try {
            const requestAnimationFrame = getRequestAnimationFrame();
            return await new Promise((resolvePromise) => requestAnimationFrame(resolvePromise));
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DomObserver', 'Animation frame failed', runtimeError);
            throw runtimeError;
        }
    }

    static async nextTick(): Promise<void> {
        try {
            await Promise.resolve();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('DomObserver', 'Next tick failed', runtimeError);
            throw runtimeError;
        }
    }
}

export { DomObserver, observeMutationsUntil };
export type { ObserveMutationsOptions };
