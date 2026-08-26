/* SoAI - OAuth popup flow controller [frontend/assets/ts/features/settings/oauthPopupFlowController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import { startPollingLoop, type PollingLoopHandle } from '@core/concurrency/pollingLoop.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { securityApi } from '@core/security/public.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { isTerminalSettingsOauthStatus } from '@features/settings/oauthValues.ts';

interface OAuthPopupResult {
    ok: boolean;
    oauthStatus: OauthStatus | null;
}

interface OAuthPopupFlowOptions {
    redirectUrl: string;
    pollStatus: () => Promise<OauthStatus>;
    logContext: string;
    startFailureMessage: string;
    statusFailureMessage: string;
}

const MAX_CONSECUTIVE_STATUS_FAILURES = 5;

const openOauthPopupAndWait = async (options: OAuthPopupFlowOptions): Promise<OAuthPopupResult> => {
    const sanitizedUrl = securityApi.sanitizeAbsoluteHttpUrl(options.redirectUrl);
    if (!sanitizedUrl) {
        throw new Error(options.startFailureMessage);
    }
    const popup = window.open(sanitizedUrl, '_blank', 'popup=yes,width=600,height=700,noopener,noreferrer');
    if (!popup) {
        throw new Error(options.startFailureMessage);
    }
    const completion = createDeferred<OAuthPopupResult>();
    const resources = new ResourceTracker();
    let settled = false;
    let lastOauthStatus: OauthStatus | null = null;
    let consecutiveStatusFailures = 0;
    let pollingHandle: PollingLoopHandle | null = null;
    const closePopupSafe = (context: string): void => {
        try {
            popup.close();
        } catch (error) {
            errorHandler.warn(options.logContext, `Failed to close OAuth popup (${context})`, ensureError(error));
        }
    };
    const resolveCompletion = (result: OAuthPopupResult, context: string): void => {
        if (settled) {
            return;
        }
        settled = true;
        pollingHandle?.stop(`oauth-popup-${context}`);
        pollingHandle = null;
        resources.cleanup();
        closePopupSafe(context);
        completion.resolve(result);
    };
    const rejectCompletion = (error: Error, context: string): void => {
        if (settled) {
            return;
        }
        settled = true;
        pollingHandle?.stop(`oauth-popup-${context}`);
        pollingHandle = null;
        resources.cleanup();
        closePopupSafe(context);
        completion.reject(error);
    };
    const handleStatusFailure = (error: Error, phase: string): 'continue' | 'stop' => {
        if (popup.closed) {
            errorHandler.warn(options.logContext, `OAuth popup closed after ${phase} status poll failure`, error);
            resolveCompletion({ ok: false, oauthStatus: lastOauthStatus }, `closed-after-${phase}-error`);
            return 'stop';
        }
        consecutiveStatusFailures += 1;
        errorHandler.warn(options.logContext, `OAuth status poll failed (${String(consecutiveStatusFailures)}/${String(MAX_CONSECUTIVE_STATUS_FAILURES)})`, error);
        if (consecutiveStatusFailures < MAX_CONSECUTIVE_STATUS_FAILURES) {
            return 'continue';
        }
        rejectCompletion(new Error(options.statusFailureMessage), 'poll-failed');
        return 'stop';
    };

    resources.setTimeout(() => {
        rejectCompletion(new Error(options.statusFailureMessage), 'timeout');
    }, minutesToMs(10));

    pollingHandle = startPollingLoop({
        label: 'settings-oauth-popup',
        intervalMs: 1000,
        initialDelayMs: 1000,
        run: async (): Promise<'continue' | 'stop'> => {
            if (popup.closed) {
                resolveCompletion({ ok: false, oauthStatus: lastOauthStatus }, 'closed-before-poll');
                return 'stop';
            }
            let pollPromise: Promise<OauthStatus>;
            try {
                pollPromise = options.pollStatus();
            } catch (error) {
                return handleStatusFailure(ensureError(error), 'synchronous');
            }
            let normalized: OauthStatus;
            try {
                normalized = await pollPromise;
            } catch (error) {
                return handleStatusFailure(ensureError(error), 'asynchronous');
            }
            if (settled) {
                return 'stop';
            }
            consecutiveStatusFailures = 0;
            lastOauthStatus = normalized;
            if (!isTerminalSettingsOauthStatus(normalized)) {
                if (popup.closed) {
                    resolveCompletion({ ok: false, oauthStatus: lastOauthStatus }, 'closed');
                    return 'stop';
                }
                return 'continue';
            }
            resolveCompletion({ ok: normalized === 'ready', oauthStatus: normalized }, 'completed');
            return 'stop';
        }
    });

    if (popup.closed) {
        resolveCompletion({ ok: false, oauthStatus: lastOauthStatus }, 'closed-immediately');
    }

    return await completion.promise;
};

export { openOauthPopupAndWait };
export type { OAuthPopupResult, OAuthPopupFlowOptions };
