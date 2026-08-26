/* SoAI - Settings page effects [frontend/assets/ts/pages/settings/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import type { ApiKeyCreateRequest } from '@core/api/contracts/apiKeyContracts.ts';
import type { ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import type { AclPolicyOverrides, AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import type { SanitizerInput } from '@core/pagecontext/contracts.ts';
import type { ApiKey, BackupApiEntry, BackupEntry, BackupListLoadStatus, BackupOperationState } from '@core/settings/contracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { ApiKeysManager, SecurityManager } from '@features/settings/public.ts';
import type { OperationType } from '@features/overlays/public.ts';
import { AclManager } from '@pages/settings/controllers/AclManager.ts';
import { BackupManager } from '@pages/settings/controllers/backupmanager/BackupManager.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { buildAdminHostBindings, buildBaseHostBindings } from '@pages/settings/controllers/page/hostBindings.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { showRestartNotification } from '@pages/settings/controllers/page/pageActions.ts';
import { LicensingManager } from '@pages/settings/controllers/LicensingManager.ts';

const createAdminSettingsManagers = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    if (!page.owners.auth.isAdmin()) {
        return;
    }
    const adminBindings = buildAdminHostBindings(page, callbacks);
    state.aclManager = new AclManager({
        availability: {
            get: () => state.aclAvailability,
            set: (availability): void => {
                state.aclAvailability = availability;
            }
        },
        host: {
            ...adminBindings,
            notifySaveChanged: callbacks.notifySaveChanged,
            syncManualDirtyField: callbacks.syncManualDirtyField,
            clearManualDirtyField: callbacks.clearManualDirtyField,
            getPolicy: () => page.owners.api.webui.acl.getPolicy(),
            updatePolicy: (payload: AclPolicyOverrides) => page.owners.api.webui.acl.updatePolicy(payload),
            sanitizeAttribute: (value: SanitizerInput): string => page.owners.pageContext.sanitizer.attribute(value),
            updateProperty: (element: Element, property: string, value: DomPropertyValue): void => page.owners.pageDom.updateProperty(element, property, value),
            updatePreferenceToggleLabel: callbacks.updatePreferenceToggleLabel,
            getAclPolicy: (): AclPolicyResponse | null => state.aclPolicy,
            setAclPolicy: (policy: AclPolicyResponse): void => {
                state.aclPolicy = policy;
            }
        }
    });
    state.apiKeysManager = new ApiKeysManager({
        host: {
            api: {
                isAdmin: adminBindings.isAdmin,
                listApiKeys: (includeRevoked: boolean) => page.owners.api.webui.apiKeys.list(includeRevoked),
                createApiKey: (payload: ApiKeyCreateRequest) => page.owners.api.webui.apiKeys.create(payload),
                revokeApiKey: (keyId: string) => page.owners.api.webui.apiKeys.revoke(keyId),
                rotateApiKey: (keyId: string) => page.owners.api.webui.apiKeys.rotate(keyId),
                deleteApiKey: (keyId: string) => page.owners.api.webui.apiKeys.delete(keyId),
                deleteAllApiKeys: () => page.owners.api.webui.apiKeys.deleteAll(),
                getApiKeyQuota: (keyId: string) => page.owners.api.webui.apiKeys.getQuota(keyId),
                updateApiKeyQuota: (keyId: string, payload: ApiKeyQuotaUpdateRequest) => page.owners.api.webui.apiKeys.updateQuota(keyId, payload),
                listApiKeyQuotaStatus: () => page.owners.api.webui.apiKeys.listQuotaStatus(),
                assignApiKeyToUser: (keyId: string, userId: number) => page.owners.api.webui.apiKeys.assignUser(keyId, userId),
                unassignApiKeyFromUser: (keyId: string) => page.owners.api.webui.apiKeys.unassignUser(keyId),
                listUsers: async (): Promise<Array<{ id: number; username: string }>> => {
                    const users = await page.owners.api.webui.users.list();
                    return users.map((user) => ({ id: Number(user.id), username: String(user.username) }));
                },
                sanitizeHtml: (value: SanitizerInput): string => page.owners.pageContext.sanitizer.html(value),
                sanitizeAttribute: (value: SanitizerInput): string => page.owners.pageContext.sanitizer.attribute(value)
            },
            view: {
                pageDom: page.owners.pageDom,
                pageResources: page.owners.pageResources,
                updatePreferenceToggleLabel: callbacks.updatePreferenceToggleLabel,
                setTimer: (callback: () => void, delayMs: number): number | null => page.owners.pageResources.setTimer(callback, delayMs),
                clearTimer: (timerId: number | null): void => page.owners.pageResources.clearTimer(timerId)
            },
            execution: {
                feedback: page.owners.feedback,
                runWithBoundary: (name, task) => page.owners.pageLifecycle.run(name, task),
                confirmAndExecute: callbacks.confirmAndExecute
            },
            notifications: { feedback: page.owners.feedback },
            search: {
                hasSearchQuery: adminBindings.hasSearchQuery,
                filterSettings: callbacks.filterSettings
            },
            state: {
                getApiKeys: (): ApiKey[] => state.apiKeys,
                setApiKeys: (keys: ApiKey[]): void => {
                    state.apiKeys = keys;
                },
                getApiKeyQuotaSummaries: () => state.apiKeyQuotaSummaries,
                setApiKeyQuotaSummaries: (summaries) => {
                    state.apiKeyQuotaSummaries = summaries;
                },
                getApiKeyQuotaSummary: (keyId: string) => state.apiKeyQuotaSummaries[keyId] ?? null,
                getShowRevokedKeys: (): boolean => state.showRevokedKeys,
                setShowRevokedKeys: (show: boolean): void => {
                    state.showRevokedKeys = show;
                }
            }
        }
    });
    state.securityManager = new SecurityManager({
        host: {
            ...adminBindings,
            rebindConfigForm: callbacks.rebindConfigForm,
            openUsersTab: (): void => {
                const tabs = page.owners.layout.getTabs();
                if (!tabs) {
                    throw new Error('Settings tabs are not initialized');
                }
                tabs.setActiveTab('users');
            },
            getCoreConfig: (): JsonObject => state.coreConfig,
            getSecurityAudit: () => state.securityAudit,
            setSecurityAudit: (audit): void => {
                state.securityAudit = audit;
            },
            getSecurityAvailability: () => state.securityAvailability,
            setSecurityAvailability: (availability): void => {
                state.securityAvailability = availability;
            },
            loadSecurityAudit: (options) => page.owners.api.system.securityHardeningAudit(options)
        }
    });
    state.licensingManager = new LicensingManager({
        licensing: {
            load: (options) => page.owners.api.webui.licensing.status(options),
            governingDocuments: (flow, options) => page.owners.api.webui.licensing.governingDocuments(flow, options),
            acceptLicense: (revision, fingerprint, options) => page.owners.api.webui.licensing.acceptLicense(revision, fingerprint, options),
            activate: (revision, productKey, options) => page.owners.api.webui.licensing.activate(revision, productKey, options),
            convertOsEvaluation: (revision, organization, legalAcceptances, options) => page.owners.api.webui.licensing.convertOsEvaluation(revision, organization, legalAcceptances, options),
            revertOsEvaluation: (revision, options) => page.owners.api.webui.licensing.revertOsEvaluation(revision, options),
            convertCommercial: (revision, input, options) => page.owners.api.webui.licensing.convertCommercial(revision, input, options),
            reclassify: (revision, environment, options) => page.owners.api.webui.licensing.reclassify(revision, environment, options),
            retrieveTerm: (revision, options) => page.owners.api.webui.licensing.retrieveTerm(revision, options),
            reconcile: (revision, options) => page.owners.api.webui.licensing.reconcile(revision, options),
            deactivate: (reason, options) => page.owners.api.webui.licensing.deactivate(reason, options),
            exportOffline: async (revision, environment, options) => {
                const response = await page.owners.api.webui.licensing.exportOfflineRequest(revision, environment, options);
                await downloadAuthenticatedResponse(response);
                return page.owners.api.webui.licensing.status(options);
            },
            importOffline: (revision, file, options) => page.owners.api.webui.licensing.importOfflineCertificate(revision, file, options),
            changeDeclaration: async (revision, declaration, attestation, options) => {
                const status = await page.owners.api.webui.licensing.changeDeclaration(revision, declaration, attestation, options);
                await showRestartNotification(page, state);
                return status;
            }
        },
        system: {
            loadVersion: async (options) => (await page.owners.api.system.info(options)).soaiVersion
        },
        page: {
            confirmDeactivation: () =>
                requireDialogsService().showConfirmation({
                    title: i18n.t('settings.licensing.deactivateConfirmTitle'),
                    message: i18n.t('settings.licensing.deactivateConfirmMessage'),
                    confirmText: i18n.t('settings.licensing.deactivate'),
                    cancelText: i18n.t('common.cancel')
                }),
            openPowerPage: () => page.owners.router.navigate('power'),
            subscribeStatusChanged: (callback) => subscribeManagedWebSocketContract({ label: 'LicensingManager', contract: WEBSOCKET_EVENT_CONTRACTS.licensing.statusChanged, handler: callback }),
            notify: (message, type) => page.owners.feedback.show(message, type)
        },
        view: {
            requireContainer: () => page.owners.pageDom.require('licensing-content'),
            updateHtml: (container, markup) => page.owners.pageDom.updateHtml(container, markup),
            bindEvent: (container, event, listener) => page.owners.pageResources.on(container, event, listener),
            filter: callbacks.filterSettings,
            hasSearchQuery: adminBindings.hasSearchQuery
        }
    });
    state.backupManager = new BackupManager({
        host: {
            api: {
                isAdmin: adminBindings.isAdmin,
                listBackups: (): Promise<{ backups: BackupApiEntry[] }> => page.owners.api.webui.admin.backups.list(),
                createBackup: () => page.owners.api.webui.admin.backups.create(),
                restoreBackup: (backupId: string) => page.owners.api.webui.admin.backups.restore(backupId),
                verifyBackup: (backupId: string) => page.owners.api.webui.admin.backups.verify(backupId),
                deleteBackup: (backupId: string) => page.owners.api.webui.admin.backups.remove(backupId),
                exportBackup: (backupId: string) => page.owners.api.webui.admin.backups.export(backupId),
                restartApplication: () => page.owners.api.system.power.restartApplication(),
                showRestartOverlay: (value: OperationType): void => state.restartOverlay.show(value),
                sanitizeHtml: (value: SanitizerInput): string => page.owners.pageContext.sanitizer.html(value),
                sanitizeAttribute: (value: SanitizerInput): string => page.owners.pageContext.sanitizer.attribute(value)
            },
            dom: { pageDom: adminBindings.pageDom, pageResources: adminBindings.pageResources },
            tasks: {
                trackAcceptedTask: (taskId, options) => page.owners.streaming.runtime().tasks.trackAcceptedTask(taskId, options)
            },
            execution: { feedback: adminBindings.feedback, runWithBoundary: adminBindings.runWithBoundary, confirmAndExecute: adminBindings.confirmAndExecute },
            notifications: { feedback: adminBindings.feedback },
            search: { hasSearchQuery: adminBindings.hasSearchQuery, filterSettings: adminBindings.filterSettings },
            state: {
                getBackups: () => state.backups,
                setBackups: (backups: BackupEntry[]): void => {
                    state.backups = backups;
                },
                getBackupListLoadStatus: (): BackupListLoadStatus => state.backupListLoadStatus,
                setBackupListLoadStatus: (status: BackupListLoadStatus): void => {
                    state.backupListLoadStatus = status;
                },
                getBackupOperation: (): BackupOperationState | null => state.backupOperation,
                setBackupOperation: (operation: BackupOperationState | null): void => {
                    state.backupOperation = operation;
                }
            }
        }
    });
    if (state.productSettingsEnabled) {
        const hostApi = page.owners.api.os;
        if (hostApi === null) {
            throw new Error('Trusted host management API is unavailable for the selected frontend edition');
        }
        const settingsContribution = page.edition.product;
        if (settingsContribution === null) {
            throw new Error('Trusted host settings contribution is unavailable for the selected frontend edition');
        }
        const managers = settingsContribution.createManagers(
            {
                ...buildBaseHostBindings(page, callbacks),
                withButtonDisabled: callbacks.withButtonDisabled,
                confirmAndExecute: callbacks.confirmAndExecute
            },
            hostApi,
            page.owners.api.tasks
        );
        state.productManagers = managers;
    }
};

export { createAdminSettingsManagers };
