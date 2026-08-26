/* SoAI - Settings feature quota live updates [frontend/assets/ts/features/settings/apikeys/quotaLiveUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { optionalTrimmedDataAttribute, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { reconcileElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import { appendHtml, insertHtmlBefore } from '@core/dom/html.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { applyProgressWidths } from '@core/ui/progressWidths.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { decodeApiKeyQuotaStatusListResponse } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import { findApiKeyActionsElement, findApiKeyInfoElement, findApiKeyQuotaModalStatusElement, findApiKeyQuotaModeBadgeElement, findApiKeyQuotaSummaryElement, findApiKeyStatusBadgeElement, listApiKeyItems, optionalApiKeyQuotaModal } from '@features/settings/apikeys/dom.ts';
import { renderApiKeyQuotaStatusPreview } from '@features/settings/apikeys/quotaModalMarkup.ts';
import { renderApiKeyQuotaModeBadge, renderApiKeyQuotaSummary } from '@features/settings/apikeys/quotaSummaryView.ts';
import type { ApiKeysManagerHost } from '@features/settings/apikeys/types.ts';

type ApiKeyQuotaSummaries = ReturnType<typeof decodeApiKeyQuotaStatusListResponse>;

interface StartApiKeyQuotaLiveUpdatesArguments {
    host: ApiKeysManagerHost;
    root: HTMLElement;
    getIsMounted: () => boolean;
    getIsReloading: () => boolean;
    getUpdateGeneration: () => number;
    getRequestInFlight: () => boolean;
    setRequestInFlight: (value: boolean) => void;
    setTimerId: (timerId: number | null) => void;
    clearTimer: () => void;
}

const parseRenderedElement = (owner: HTMLElement, markup: TrustedHtml, errorMessage: string): HTMLElement => {
    const element = parseSingleRootElement({
        documentRef: owner.ownerDocument,
        html: markup,
        context: owner
    });
    if (element === null) {
        throw new Error(errorMessage);
    }
    return element;
};

const patchRenderedElement = (target: HTMLElement, source: HTMLElement): boolean => {
    if (target.outerHTML === source.outerHTML) {
        return false;
    }
    let changed = syncElementShell({ target, source });
    if (replaceChildrenIfChanged(target, source)) {
        changed = true;
    }
    return changed;
};

const applyQuotaSummariesLive = (host: ApiKeysManagerHost, root: HTMLElement, summaries: ApiKeyQuotaSummaries): void => {
    host.state.setApiKeyQuotaSummaries(summaries);
    listApiKeyItems(root).forEach((apiKeyItem) => {
        const keyId = requireTrimmedDataAttribute(apiKeyItem, 'key-id', 'API key quota item');
        syncQuotaModeBadge(host, apiKeyItem, keyId);
        const existingSummary = findApiKeyQuotaSummaryElement(apiKeyItem);
        const nextMarkup = renderApiKeyQuotaSummary(host, keyId);
        if (!nextMarkup.html) {
            existingSummary?.remove();
            return;
        }
        if (existingSummary) {
            const nextSummary = parseRenderedElement(apiKeyItem, nextMarkup, 'API key quota summary render did not produce an element');
            patchRenderedElement(existingSummary, nextSummary);
            applyProgressWidths(apiKeyItem, (element: Element, property: string, value: string | null): void => host.view.pageDom.updateStyle(element, property, value));
            return;
        }
        const infoElement = findApiKeyInfoElement(apiKeyItem);
        if (!infoElement) {
            return;
        }
        const actionsElement = findApiKeyActionsElement(infoElement);
        if (actionsElement) {
            insertHtmlBefore({ reference: actionsElement, html: nextMarkup.html, context: infoElement });
            applyProgressWidths(apiKeyItem, (element: Element, property: string, value: string | null): void => host.view.pageDom.updateStyle(element, property, value));
            return;
        }
        appendHtml({ element: infoElement, html: nextMarkup.html, context: infoElement });
        applyProgressWidths(apiKeyItem, (element: Element, property: string, value: string | null): void => host.view.pageDom.updateStyle(element, property, value));
    });
    const quotaModal = optionalApiKeyQuotaModal();
    if (!quotaModal) {
        return;
    }
    const keyId = optionalTrimmedDataAttribute(quotaModal, 'key-id');
    if (!keyId) {
        return;
    }
    const summary = summaries[keyId] ?? null;
    if (!summary) {
        return;
    }
    const statusContainer = findApiKeyQuotaModalStatusElement(quotaModal);
    if (!statusContainer) {
        return;
    }
    reconcileElementChildrenFromTrustedHtml({ target: statusContainer, html: renderApiKeyQuotaStatusPreview(host, summary), context: statusContainer });
    applyProgressWidths(statusContainer, (element: Element, property: string, value: string | null): void => host.view.pageDom.updateStyle(element, property, value));
};

const syncQuotaModeBadge = (host: ApiKeysManagerHost, apiKeyItem: HTMLElement, keyId: string): void => {
    const existingBadge = findApiKeyQuotaModeBadgeElement(apiKeyItem);
    const nextMarkup = renderApiKeyQuotaModeBadge(host, keyId);
    if (!nextMarkup.html) {
        existingBadge?.remove();
        return;
    }
    const statusBadge = findApiKeyStatusBadgeElement(apiKeyItem);
    if (!statusBadge) {
        throw new Error('API key status badge is required for quota mode badge');
    }
    const nextBadge = parseRenderedElement(apiKeyItem, nextMarkup, 'API key quota mode badge render did not produce an element');
    if (existingBadge) {
        patchRenderedElement(existingBadge, nextBadge);
        return;
    }
    statusBadge.after(nextBadge);
};

const startApiKeyQuotaLiveUpdates = ({ host, root, getIsMounted, getIsReloading, getUpdateGeneration, getRequestInFlight, setRequestInFlight, setTimerId, clearTimer }: StartApiKeyQuotaLiveUpdatesArguments): (() => void) => {
    let cancelled = false;
    const schedule = (delayMs: number): void => {
        if (cancelled) {
            return;
        }
        clearTimer();
        const timerId = host.view.setTimer(() => {
            terminateHandledPromise(tick());
        }, delayMs);
        if (timerId === null) {
            cancelled = true;
            errorHandler.debug('Settings', 'Failed to allocate API key quota live update timer');
            return;
        }
        setTimerId(timerId);
    };
    const tick = async (): Promise<void> => {
        if (cancelled || !getIsMounted()) {
            return;
        }
        if (document.hidden) {
            schedule(15000);
            return;
        }
        if (getIsReloading()) {
            schedule(1000);
            return;
        }
        if (getRequestInFlight()) {
            schedule(2000);
            return;
        }
        const generationToken = getUpdateGeneration();
        setRequestInFlight(true);
        let nextDelayMs = 2000;
        try {
            const payload = await requestWebSocketSnapshotPayload('openai_api_keys.quota.status');
            if (cancelled || !getIsMounted() || getIsReloading() || generationToken !== getUpdateGeneration()) {
                return;
            }
            const summaries = decodeApiKeyQuotaStatusListResponse(payload);
            applyQuotaSummariesLive(host, root, summaries);
        } catch (error) {
            nextDelayMs = 10000;
            const runtimeError = ensureError(error);
            errorHandler.debug('Settings', 'API key quota live update failed', runtimeError);
        } finally {
            setRequestInFlight(false);
            if (!cancelled && getIsMounted()) {
                schedule(nextDelayMs);
            }
        }
    };
    schedule(0);
    return () => {
        cancelled = true;
        clearTimer();
    };
};

export { startApiKeyQuotaLiveUpdates };
