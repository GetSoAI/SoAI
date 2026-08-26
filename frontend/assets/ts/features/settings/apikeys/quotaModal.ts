/* SoAI - Settings feature quota modal [frontend/assets/ts/features/settings/apikeys/quotaModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { requireButtonElement, requireInputElement, requireSelectElement, type ElementResolver } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createFormChangeSurfaceTracker } from '@core/forms/formChangeSurfaceTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import type { ApiKey, ApiKeyQuotaSummary } from '@core/settings/contracts.ts';
import type { ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { applyProgressWidths } from '@core/ui/progressWidths.ts';
import { API_KEYS_QUOTA_MODAL_ID } from '@features/settings/apikeys/constants.ts';
import { API_KEY_QUOTA_MODAL_BODY_CONTAINER_ID, API_KEY_QUOTA_MODAL_FOOTER_CONTAINER_ID, settingsApiKeyQuotaModalDefinition } from '@features/settings/apikeys/quotaModalDefinition.ts';
import { buildApiKeyQuotaModalBody, buildApiKeyQuotaModalFooter, type QuotaModalUsers } from '@features/settings/apikeys/quotaModalMarkup.ts';
import { buildQuotaUpdatePayload, coerceQuotaMode, readOptionalPositiveInt, setInputsEnabled } from '@features/settings/apikeys/quotaModalPayload.ts';
import type { ApiKeysManagerHost } from '@features/settings/apikeys/types.ts';

const MODAL_ID = API_KEYS_QUOTA_MODAL_ID;

const fetchUserAssignment = async (host: ApiKeysManagerHost, key: ApiKey): Promise<QuotaModalUsers | null> => {
    if (!host.api.isAdmin()) {
        return null;
    }
    try {
        const users = await host.api.listUsers();
        return {
            users,
            assignedUserId: key.assignedUserId ?? null
        };
    } catch (fetchError) {
        const runtimeError = ensureError(fetchError);
        errorHandler.warn('ApiKeyQuotaModal', 'Failed to fetch users for assignment dropdown', runtimeError);
        return null;
    }
};

const showApiKeyQuotaModal = async (host: ApiKeysManagerHost, key: ApiKey, summary: ApiKeyQuotaSummary): Promise<ApiKeyQuotaSummary | null> => {
    const presenter = requireModalPresenter();
    const userAssignment = await fetchUserAssignment(host, key);

    return await runModalSession<ApiKeyQuotaSummary | null>({
        presenter,
        modalId: MODAL_ID,
        onAlreadyOpen: 'replace',
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
            const title = i18n.t('settings.apiKeys.quota.modal.title');
            const body = buildApiKeyQuotaModalBody(host, key, summary, MODAL_ID, userAssignment);
            const footer = buildApiKeyQuotaModalFooter(host, MODAL_ID);
            modal.classList.add('api-key-quota-modal');
            modal.setAttribute('aria-label', title);
            modal.dataset['keyId'] = summary.keyId;
            const resolver: ElementResolver = createModalElementResolver(modal, 'Settings API key quota modal');
            const bodyContainer = resolver.requireHTMLElement(`#${API_KEY_QUOTA_MODAL_BODY_CONTAINER_ID}`);
            const footerContainer = resolver.requireHTMLElement(`#${API_KEY_QUOTA_MODAL_FOOTER_CONTAINER_ID}`);
            replaceChildrenFromTrustedHtml({ element: bodyContainer, html: body });
            replaceChildrenFromTrustedHtml({ element: footerContainer, html: footer });

            const modeSelectElement = requireSelectElement(resolver, modalUiSelector(MODAL_ID, 'mode'), 'ApiKeyQuotaModal mode select', modal);
            const assignedUserSelectElement = userAssignment ? requireSelectElement(resolver, modalUiSelector(MODAL_ID, 'assigned-user'), 'ApiKeyQuotaModal assigned user select', modal) : null;
            const saveButtonElement = requireButtonElement(resolver, modalUiSelector(MODAL_ID, 'save'), 'ApiKeyQuotaModal save button', modal);
            const hourlyLimitInput = requireInputElement(resolver, modalUiSelector(MODAL_ID, 'hourly-limit'), 'ApiKeyQuotaModal hourly limit input', modal);
            const hourlyWindowInput = requireInputElement(resolver, modalUiSelector(MODAL_ID, 'hourly-window'), 'ApiKeyQuotaModal hourly window input', modal);
            const dailyLimitInput = requireInputElement(resolver, modalUiSelector(MODAL_ID, 'daily-limit'), 'ApiKeyQuotaModal daily limit input', modal);
            const weeklyLimitInput = requireInputElement(resolver, modalUiSelector(MODAL_ID, 'weekly-limit'), 'ApiKeyQuotaModal weekly limit input', modal);
            const monthlyLimitInput = requireInputElement(resolver, modalUiSelector(MODAL_ID, 'monthly-limit'), 'ApiKeyQuotaModal monthly limit input', modal);
            const windowInputs: HTMLInputElement[] = [hourlyLimitInput, hourlyWindowInput, dailyLimitInput, weeklyLimitInput, monthlyLimitInput];
            const limitSettingItems = dom.resolveAll('.api-key-quota-modal .settings-group .setting-item:not(.full-width)', modal).filter((element): element is HTMLElement => element instanceof HTMLElement);
            const changeSurfaces = createFormChangeSurfaceTracker(modal);
            const baselineAssignedUserId = userAssignment?.assignedUserId ?? null;
            const getSelectedUserId = (): number | null => {
                if (!assignedUserSelectElement) {
                    return null;
                }
                const parsed = readRuntimeFiniteNumberOrFallbackValue(readTrimmedSelectValue(assignedUserSelectElement), null);
                return parsed !== null && parsed > 0 ? Math.trunc(parsed) : null;
            };
            const hasAssignmentChanged = (): boolean => {
                if (!assignedUserSelectElement) {
                    return false;
                }
                return getSelectedUserId() !== baselineAssignedUserId;
            };
            const baselinePayloadKey = (() => {
                try {
                    return JSON.stringify(
                        buildQuotaUpdatePayload(summary.config.mode, {
                            hourlyLimit: summary.config.hourly?.limitUnits ?? null,
                            hourlyWindowHours: summary.config.hourly?.windowHours ?? null,
                            dailyLimit: summary.config.daily?.limitUnits ?? null,
                            weeklyLimit: summary.config.weekly?.limitUnits ?? null,
                            monthlyLimit: summary.config.monthly?.limitUnits ?? null
                        })
                    );
                } catch (baselineError) {
                    const runtimeError = ensureError(baselineError);
                    errorHandler.warn('ApiKeyQuotaModal', 'Failed to build baseline payload key', runtimeError);
                    return '';
                }
            })();
            const buildPayloadFromForm = (): ApiKeyQuotaUpdateRequest => {
                const mode = coerceQuotaMode(modeSelectElement.value);
                if (mode === 'none') {
                    return { mode };
                }
                return buildQuotaUpdatePayload(mode, {
                    hourlyLimit: readOptionalPositiveInt(hourlyLimitInput),
                    hourlyWindowHours: readOptionalPositiveInt(hourlyWindowInput),
                    dailyLimit: readOptionalPositiveInt(dailyLimitInput),
                    weeklyLimit: readOptionalPositiveInt(weeklyLimitInput),
                    monthlyLimit: readOptionalPositiveInt(monthlyLimitInput)
                });
            };
            const computeFormState = (): { hasChanges: boolean; isValid: boolean } => {
                try {
                    const payloadKey = JSON.stringify(buildPayloadFromForm());
                    const quotaChanged = payloadKey !== baselinePayloadKey;
                    const assignmentChanged = hasAssignmentChanged();
                    return { hasChanges: quotaChanged || assignmentChanged, isValid: true };
                } catch (formStateError) {
                    const runtimeError = ensureError(formStateError);
                    errorHandler.warn('ApiKeyQuotaModal', 'Failed to compute form state', runtimeError);
                    return { hasChanges: true, isValid: false };
                }
            };

            const applyModeState = (): void => {
                const mode = coerceQuotaMode(modeSelectElement.value);
                setInputsEnabled(windowInputs, mode !== 'none');
                limitSettingItems.forEach((item) => {
                    item.classList.toggle('u-hidden', mode === 'none');
                });
                changeSurfaces.sync();
                save.notifyChanged();
            };
            const setQuotaControlsSaving = (saving: boolean): void => {
                const targets: Array<HTMLInputElement | HTMLSelectElement> = [modeSelectElement, ...windowInputs];
                if (assignedUserSelectElement) {
                    targets.push(assignedUserSelectElement);
                }
                for (const target of targets) {
                    if (saving) {
                        setBusyDisabledState(target, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken, spinner: 'none' });
                        continue;
                    }
                    const token = getBusyDisabledToken(target);
                    if (token) {
                        setBusyDisabledState(target, { isBusy: false, token });
                    }
                }
                if (!saving) {
                    applyModeState();
                }
                save.notifyChanged();
            };

            const performSave = async (): Promise<void> => {
                const { hasChanges, isValid } = computeFormState();
                if (!hasChanges || !isValid) {
                    return;
                }
                const payload = (() => {
                    try {
                        return buildPayloadFromForm();
                    } catch (payloadError) {
                        const runtimeError = ensureError(payloadError);
                        errorHandler.warn('ApiKeyQuotaModal', 'Failed to build quota payload from form', runtimeError);
                        host.notifications.feedback.show(i18n.t('settings.apiKeys.quota.notifications.validationError'), 'warning');
                        return null;
                    }
                })();
                if (!payload) {
                    save.notifyChanged();
                    return;
                }
                const assignmentChanged = hasAssignmentChanged();
                const selectedUserId = getSelectedUserId();
                const quotaPayloadKey = JSON.stringify(payload);
                const quotaChanged = quotaPayloadKey !== baselinePayloadKey;
                try {
                    await host.execution.runWithBoundary('settings:updateApiKeyQuota', async () => {
                        let nextSummary = summary;
                        if (assignmentChanged) {
                            if (selectedUserId !== null) {
                                await host.api.assignApiKeyToUser(summary.keyId, selectedUserId);
                            } else {
                                await host.api.unassignApiKeyFromUser(summary.keyId);
                            }
                        }
                        if (quotaChanged) {
                            nextSummary = await host.api.updateApiKeyQuota(summary.keyId, payload);
                        }
                        setResult(nextSummary);
                        host.notifications.feedback.show(i18n.t('settings.apiKeys.quota.notifications.updateSuccess'), 'success');
                        close('confirm');
                    });
                } catch (saveError) {
                    const runtimeError = ensureError(saveError);
                    errorHandler.warn('ApiKeyQuotaModal', 'Quota save boundary failed', runtimeError);
                    throw runtimeError;
                }
            };

            const save = createSaveController({
                headerContextId: `${MODAL_ID}:${summary.keyId}`,
                headerPriority: SAVE_HEADER_PRIORITY_MODAL,
                requestContextLabel: 'ApiKeyQuotaModal save',
                units: [
                    {
                        id: 'api-key-quota',
                        hasChanges: () => computeFormState().hasChanges,
                        isValid: () => computeFormState().isValid,
                        save: async () => performSave()
                    }
                ]
            });

            setAriaBusy(modal, false);
            setQuotaControlsSaving(false);
            save.attach({
                resolveSaveButtons: () => [saveButtonElement],
                onBusyChange: (busy: boolean) => setQuotaControlsSaving(busy),
                busyRoots: [modal],
                autoNotifyRoot: modal
            });
            changeSurfaces.captureBaseline();
            applyProgressWidths(modal, (element: Element, property: string, value: string | null): void => host.view.pageDom.updateStyle(element, property, value));
            const syncChangeSurfaces = (): void => {
                changeSurfaces.sync();
            };
            modeSelectElement.addEventListener('change', applyModeState, { signal });
            modal.addEventListener('input', syncChangeSurfaces, { signal });
            modal.addEventListener('change', syncChangeSurfaces, { signal });
            applyModeState();

            const dispose = (): void => {
                setAriaBusy(modal, false);
                setQuotaControlsSaving(false);
                changeSurfaces.clear();
                save.dispose();
                bodyContainer.textContent = '';
                footerContainer.textContent = '';
                delete modal.dataset['keyId'];
            };

            return { dispose };
        }
    });
};
export { settingsApiKeyQuotaModalDefinition, showApiKeyQuotaModal };
