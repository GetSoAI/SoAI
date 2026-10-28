/* SoAI - Shared DOM observer [frontend/assets/ts/core/dom/domObserver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDomDocument, getDomWindow } from '@core/dom/domEnvironment.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFiniteNumber, isNode } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ObserveMutationsOptions {
    root?: Node;
    timeout?: number;
    rejectionMessage?: string;
    includeAttributes?: boolean;
    signal?: AbortSignal | null;
}

const observeMutationsUntil = <T>(evaluator: () => T | null | undefined | false, { root = getDomDocument(), timeout = 0, rejectionMessage = 'Timeout waiting for condition', includeAttributes = false, signal = null }: ObserveMutationsOptions = {}): Promise<T> => {
    return new Promise((resolvePromise, rejectPromise) => {
        throwIfAborted(signal);
        let timerId: number | null = null;
        let active = true;
        const deadline = isFiniteNumber(timeout) && timeout > 0 ? monotonicMs() + timeout : null;
        const finalize = (callback: () => void): void => {
            if (!active) return;
            active = false;
            observer.disconnect();
            signal?.removeEventListener('abort', onAbort);
            if (timerId !== null) getDomWindow().clearTimeout(timerId);
            callback();
        };
        const onAbort = (): void => finalize(() => rejectPromise(createAbortError()));
        const evaluate = (): void => {
            if (!active) return;
            if (deadline !== null && monotonicMs() >= deadline) {
                finalize(() => rejectPromise(new Error(rejectionMessage)));
                return;
            }
            try {
                const result = evaluator();
                if (result !== null && result !== undefined && result !== false) finalize(() => resolvePromise(result));
            } catch (error) {
                finalize(() => rejectPromise(ensureError(error)));
            }
        };
        const observer = new MutationObserver(evaluate);
        try {
            observer.observe(root, { childList: true, subtree: true, attributes: includeAttributes });
            signal?.addEventListener('abort', onAbort, { once: true });
            if (deadline !== null) timerId = getDomWindow().setTimeout(() => finalize(() => rejectPromise(new Error(rejectionMessage))), timeout);
            evaluate();
        } catch (error) {
            finalize(() => rejectPromise(ensureError(error)));
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
