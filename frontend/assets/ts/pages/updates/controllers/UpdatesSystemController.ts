/* SoAI - Updates page system controller [frontend/assets/ts/pages/updates/controllers/UpdatesSystemController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { requestUpdatesSystemPayload } from '@pages/updates/controllers/updatesSystemCheckRequestController.ts';
import type { SystemUiRefs, UpdatesSystemControllerHost } from '@pages/updates/controllers/UpdatesSystemControllerContract.ts';
import type { SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';
import { buildUpdatesReleaseNotesMarkup, buildUpdatesSummaryMarkup } from '@pages/updates/controllers/UpdatesSystemMarkupBuilder.ts';
import { normalizeUpdatePayload, normalizeUpdatesSystemErrorMessage } from '@pages/updates/controllers/UpdatesSystemPayloadParser.ts';
import { clearUpdatesSystemDetails, setUpdatesSystemStatus } from '@pages/updates/controllers/UpdatesSystemStatusView.ts';
import type { UpdatesInstallOutcome, UpdatesOperationOutcome } from '@core/edition/updatesContribution.ts';

const logger = createModuleLogger('UpdatesSystemController', { defaultLevel: 'warn' });
const MAX_CHECK_ATTEMPTS = 3;
const RETRY_DELAY_MS = 600;
const MAX_ERROR_MESSAGE_LENGTH = 280;
const INSTALL_ICON_OPTIONS = Object.freeze({ size: 12, strokeWidth: 1.2 });
const GENERIC_UPDATE_FAILURE_MESSAGES = Object.freeze(['update check failed.', 'failed to check for updates']);

interface UpdatesSystemCheckOptions {
    manageButtonLoading?: boolean | undefined;
    notifyOnFailure?: boolean | undefined;
}

interface UpdatesSystemInstallOutcome extends UpdatesInstallOutcome {
    operationRevision: number | null;
}

class UpdatesSystemController {
    #host: UpdatesSystemControllerHost;
    #ui: SystemUiRefs;
    #checkButton: HTMLButtonElement | null = null;
    #currentUpdate: ReturnType<typeof normalizeUpdatePayload> = null;
    #isChecking = false;
    #updateInProgress = false;
    #lifecycleVersion = 0;

    constructor(dependencies: { host: UpdatesSystemControllerHost; ui: SystemUiRefs }) {
        this.#host = dependencies.host;
        this.#ui = dependencies.ui;
    }

    initialize(checkButton: HTMLButtonElement): void {
        this.#checkButton = checkButton;
        checkButton.dataset['loadingText'] = i18n.t('updates.status.fetching');
        checkButton.dataset['idleText'] = i18n.t('updates.actions.checkUpdates');
        this.#setStatus({ heading: i18n.t('updates.application.status.idle'), detail: '' });
        clearUpdatesSystemDetails({
            ui: this.#ui,
            toggleHidden: this.#host.toggleHidden,
            updateHTML: this.#host.updateHTML
        });
    }

    destroy(): void {
        this.#lifecycleVersion += 1;
        this.#checkButton = null;
        this.#currentUpdate = null;
        this.#isChecking = false;
        this.#updateInProgress = false;
    }

    async checkForUpdates(options?: UpdatesSystemCheckOptions): Promise<UpdatesOperationOutcome> {
        if (this.#isChecking || !this.#checkButton) {
            return { type: 'skipped', message: '', updatesCount: 0 };
        }
        const checkButton = this.#checkButton;
        const manageButtonLoading = options?.manageButtonLoading !== false;
        const lifecycle = this.#lifecycleVersion;
        this.#isChecking = true;
        try {
            this.#setStatus({ heading: i18n.t('updates.status.fetching'), detail: '', loading: true });
            this.#host.toggleHidden(this.#ui.detailsSection, true);
            if (manageButtonLoading) {
                this.#host.setButtonLoading(checkButton, true);
            }
            const response = await requestUpdatesSystemPayload({
                checkUpdates: async () => await this.#host.api.checkUpdates(),
                wait: async (ms) => await this.#host.wait(ms),
                maxAttempts: MAX_CHECK_ATTEMPTS,
                retryDelayMs: RETRY_DELAY_MS
            });
            if (lifecycle !== this.#lifecycleVersion) {
                return { type: 'skipped', message: '', updatesCount: 0 };
            }
            if (response.payload) {
                return this.#applyUpdatePayload(response.payload);
            }
            return this.#handleCheckFailure(response.error, options?.notifyOnFailure !== false);
        } catch (error) {
            if (lifecycle !== this.#lifecycleVersion) {
                return { type: 'skipped', message: '', updatesCount: 0 };
            }
            return this.#handleCheckFailure(ensureError(error), options?.notifyOnFailure !== false);
        } finally {
            this.#isChecking = false;
            if (manageButtonLoading) {
                this.#host.setButtonLoading(checkButton, false);
            }
        }
    }

    async installSystemUpdate(button: HTMLElement): Promise<UpdatesSystemInstallOutcome> {
        if (this.#updateInProgress || !this.#currentUpdate || !this.#currentUpdate.updateAvailable) {
            return { type: 'skipped', message: '', operationRevision: null };
        }
        const lifecycle = this.#lifecycleVersion;
        const latestVersion = this.#currentUpdate.latestVersion || i18n.t('updates.unknown');
        this.#updateInProgress = true;
        let operationRevision: number | null = null;
        try {
            this.#syncInstallButtonState();
            const confirmed = await requireDialogsService().showConfirmation({
                title: i18n.t('updates.actions.installUpdate'),
                message: i18n.t('updates.confirmations.installSystem', { version: latestVersion }),
                confirmText: i18n.t('updates.actions.installUpdate'),
                cancelText: i18n.t('common.cancel'),
                variant: 'info'
            });
            if (!confirmed) {
                return { type: 'skipped', message: '', operationRevision: null };
            }

            operationRevision = this.#host.onInstallStarted();
            this.#host.setButtonLoading(button, true, { loadingText: i18n.t('updates.status.updating') });
            this.#setStatus({
                heading: i18n.t('updates.status.updating'),
                detail: `${i18n.t('updates.metadata.latest_version')} ${latestVersion}`
            });
            await this.#host.api.updateSoAI();
            if (lifecycle !== this.#lifecycleVersion) {
                return { type: 'skipped', message: '', operationRevision };
            }
            this.#host.notify(i18n.t('updates.notifications.systemUpdateInitiated'), 'success');
            this.#host.showOverlay('update-soai');
            return { type: 'started', message: i18n.t('updates.notifications.systemUpdateInitiated'), operationRevision };
        } catch (error) {
            if (lifecycle !== this.#lifecycleVersion) {
                return { type: 'skipped', message: '', operationRevision };
            }
            this.#host.handleError(ensureError(error), 'System update failed', { notify: false });
            const outcome: UpdatesSystemInstallOutcome = {
                type: 'error',
                message: i18n.t('updates.notifications.systemUpdateFailed'),
                operationRevision
            };
            this.#setStatus({
                heading: outcome.message,
                detail: '',
                error: true
            });
            return outcome;
        } finally {
            this.#updateInProgress = false;
            if (operationRevision !== null) {
                this.#host.setButtonLoading(button, false);
            }
            if (lifecycle === this.#lifecycleVersion) {
                this.#syncInstallButtonState();
            }
        }
    }

    #applyUpdatePayload(payload: SoftwareUpdateCheckResponse): UpdatesOperationOutcome {
        this.#currentUpdate = normalizeUpdatePayload(payload);
        if (!this.#currentUpdate || (!this.#currentUpdate.currentVersion && !this.#currentUpdate.latestVersion)) {
            const message = this.#resolveFailureDetail(this.#currentUpdate?.message ?? '');
            this.#setStatus({
                heading: i18n.t('updates.notifications.checkFailed'),
                detail: message,
                error: true
            });
            clearUpdatesSystemDetails({
                ui: this.#ui,
                toggleHidden: this.#host.toggleHidden,
                updateHTML: this.#host.updateHTML
            });
            return { type: 'error', message, updatesCount: 0 };
        }

        const hasUpdate = this.#currentUpdate.updateAvailable;
        const latestVersion = this.#currentUpdate.latestVersion || i18n.t('updates.unknown');
        const detail = hasUpdate ? `${i18n.t('updates.metadata.latest_version')} ${latestVersion}` : this.#currentUpdate.message || `${i18n.t('updates.metadata.latest_version')} ${latestVersion}`;
        this.#setStatus({
            heading: hasUpdate ? i18n.t('updates.sections.system.updatesAvailable', { count: 1 }) : i18n.t('updates.sections.system.upToDate'),
            detail
        });
        this.#host.toggleHidden(this.#ui.detailsSection, false);
        this.#renderSummary(this.#currentUpdate);
        this.#renderReleaseNotes(this.#currentUpdate.releaseNotes);
        this.#syncInstallButtonState();
        return {
            type: hasUpdate ? 'updatesFound' : 'noUpdates',
            message: hasUpdate ? i18n.t('updates.sections.system.updatesAvailable', { count: 1 }) : i18n.t('updates.sections.system.upToDate'),
            updatesCount: hasUpdate ? 1 : 0
        };
    }

    #renderSummary(update: NonNullable<ReturnType<typeof normalizeUpdatePayload>>): void {
        const markup = buildUpdatesSummaryMarkup({
            update,
            unknownLabel: i18n.t('updates.unknown'),
            updatesAvailableLabel: i18n.t('updates.sections.system.updatesAvailable', { count: 1 }),
            upToDateLabel: i18n.t('updates.badges.upToDate'),
            sectionTitle: i18n.t('updates.sections.system.title'),
            currentVersionLabel: i18n.t('updates.sections.system.current_version'),
            latestVersionLabel: i18n.t('updates.metadata.latest_version'),
            publishedLabel: i18n.t('updates.metadata.published'),
            releaseLinkLabel: i18n.t('updates.metadata.viewRelease'),
            installActionLabel: i18n.t('updates.actions.installUpdate'),
            installActionAriaLabel: i18n.t('updates.ariaLabels.installUpdate'),
            sanitizeHtml: this.#host.sanitizeHtml,
            sanitizeAttribute: this.#host.sanitizeAttribute,
            sanitizeUrl: this.#host.sanitizeUrl,
            getIconSync: this.#host.getIconSync,
            iconOptions: INSTALL_ICON_OPTIONS
        });
        this.#host.updateHTML(this.#ui.summaryContainer, markup, { escape: false });
    }

    #renderReleaseNotes(releaseNotes: string): void {
        const markup = buildUpdatesReleaseNotesMarkup(releaseNotes, this.#host.sanitizeHtml);
        this.#host.updateHTML(this.#ui.notesBody, markup.html, { escape: false });
        this.#host.toggleHidden(this.#ui.notesContainer, !markup.hasNotes);
    }

    #syncInstallButtonState(): void {
        const installButton = this.#host.resolveInstallButton();
        if (!installButton) {
            return;
        }
        this.#host.updateProperty(installButton, 'disabled', !this.#currentUpdate?.updateAvailable || this.#updateInProgress);
    }

    #handleCheckFailure(error: Error | null, notify = true): UpdatesOperationOutcome {
        const heading = i18n.t('updates.notifications.checkFailed');
        const message = normalizeUpdatesSystemErrorMessage(error, MAX_ERROR_MESSAGE_LENGTH);
        const detail = message ? i18n.t('updates.errors.latestResponse', { message }) : i18n.t('updates.errors.latestResponseUnavailable');
        const outcomeMessage = i18n.t('updates.errors.checkAttemptsDetail', { attempts: MAX_CHECK_ATTEMPTS, detail });
        this.#setStatus({
            heading,
            detail: outcomeMessage,
            error: true
        });
        clearUpdatesSystemDetails({
            ui: this.#ui,
            toggleHidden: this.#host.toggleHidden,
            updateHTML: this.#host.updateHTML
        });
        const runtimeError = ensureError(error);
        logger('error', `${heading}: ${message || heading}`, runtimeError);
        if (notify) {
            showOperationFailureNotification({
                error: runtimeError,
                errorMessage: message || heading,
                showNotification: (notificationMessage, level) => this.#host.notify(notificationMessage, level)
            });
        }
        return { type: 'error', message: outcomeMessage, updatesCount: 0 };
    }

    #resolveFailureDetail(message: string): string {
        const detail = message.trim();
        const normalized = detail.toLocaleLowerCase();
        if (!detail || GENERIC_UPDATE_FAILURE_MESSAGES.includes(normalized) || normalized === i18n.t('updates.notifications.checkFailed').toLocaleLowerCase()) {
            return i18n.t('updates.errors.noDetailedError');
        }
        return detail;
    }

    #setStatus(value: { heading: string; detail: string; error?: boolean | undefined; loading?: boolean | undefined }): void {
        setUpdatesSystemStatus({
            ui: this.#ui,
            updateText: this.#host.updateText,
            toggleHidden: this.#host.toggleHidden,
            heading: value.heading,
            detail: value.detail,
            error: value.error,
            loading: value.loading
        });
    }
}

export { UpdatesSystemController };
