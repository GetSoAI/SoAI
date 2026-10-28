/* SoAI - Application update history restoration and freshness presentation [frontend/assets/ts/pages/updates/controllers/applicationUpdateHistoryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serverEpochMs } from '@core/time/clock.ts';
import { decodeSoftwareUpdateCheckResponse, type SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { APPLICATION_UPDATE_HISTORY_KEY, readUpdateHistory, saveUpdateCheck, type UpdateHistory, type UpdateHistoryStorage } from '@core/updates/updateHistory.ts';
import { formatUpdateHistory } from '@core/updates/updateHistoryPresentation.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface ApplicationUpdateHistoryDependencies {
    storage: UpdateHistoryStorage;
    element: HTMLElement;
    updateText(element: Element, text: string): void;
    toggleHidden(element: Element, hidden: boolean): void;
    notify(message: string, type: 'warning'): void;
}

const serializeApplicationUpdateResult = (payload: SoftwareUpdateCheckResponse): JsonObject => ({
    'update_available': payload.updateAvailable,
    'current_version': payload.currentVersion,
    'latest_version': payload.latestVersion,
    message: payload.message,
    'release_url': payload.releaseUrl,
    'published_at': payload.publishedAt,
    'release_notes': payload.releaseNotes,
    'release_history': (payload.releaseHistory ?? []).map((entry) => ({ version: entry.version, body: entry.body, 'published_at': entry.publishedAt })),
    'release_history_complete': payload.releaseHistoryComplete ?? !payload.updateAvailable,
    'platform_id': payload.platformId,
    'delivery_type': payload.deliveryType,
    'install_supported': payload.installSupported
});

class ApplicationUpdateHistoryController {
    readonly #dependencies: ApplicationUpdateHistoryDependencies;
    saved = false;
    hasHistory = false;

    constructor(dependencies: ApplicationUpdateHistoryDependencies) {
        this.#dependencies = dependencies;
    }

    restore(): { type: 'available'; payload: SoftwareUpdateCheckResponse | null; failure: string | null } | { type: 'unavailable' } {
        try {
            const history = readUpdateHistory(this.#dependencies.storage, APPLICATION_UPDATE_HISTORY_KEY);
            const payload = history.result === null ? null : decodeSoftwareUpdateCheckResponse(history.result);
            this.saved = history.result !== null;
            this.hasHistory = history.checkedAtMs !== null || history.updatedAtMs !== null;
            this.#render(history);
            return { type: 'available', payload, failure: history.failure };
        } catch (error) {
            this.hasHistory = true;
            errorHandler.warn('Updates', 'Application update history is unavailable', ensureError(error));
            this.#showUnavailable();
            return { type: 'unavailable' };
        }
    }

    async record(payload: SoftwareUpdateCheckResponse | null, failure: string | null): Promise<void> {
        this.saved = false;
        this.hasHistory = true;
        try {
            const history = await saveUpdateCheck(this.#dependencies.storage, APPLICATION_UPDATE_HISTORY_KEY, { checkedAtMs: serverEpochMs(), result: payload === null ? null : serializeApplicationUpdateResult(payload), failure });
            this.saved = failure !== null && history.result !== null;
            this.#render(history);
        } catch (error) {
            errorHandler.warn('Updates', 'Application update history is unavailable', ensureError(error));
            this.#showUnavailable();
        }
    }

    #render(history: UpdateHistory): void {
        const text = formatUpdateHistory(history, this.saved);
        this.#dependencies.updateText(this.#dependencies.element, text);
        this.#dependencies.toggleHidden(this.#dependencies.element, !text);
    }

    #showUnavailable(): void {
        this.#dependencies.updateText(this.#dependencies.element, i18n.t('updates.history.unavailable'));
        this.#dependencies.toggleHidden(this.#dependencies.element, false);
        this.#dependencies.notify(i18n.t('updates.history.unavailable'), 'warning');
    }
}

export { ApplicationUpdateHistoryController };
