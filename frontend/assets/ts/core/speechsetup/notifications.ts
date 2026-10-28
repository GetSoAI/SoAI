/* SoAI - Notifications for observed speech setup failures [frontend/assets/ts/core/speechsetup/notifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadWebuiPermissionsSnapshot, type WebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { CleanupStack } from '@core/lifecycle/cleanupStack.ts';
import { i18n } from '@core/i18n/index.ts';
import { getLocation } from '@core/environment/public.ts';
import { buildSpeechAddModelRoute, buildSpeechModelSettingsRoute, speechSetupAskAdministratorMessage } from '@core/speechsetup/presentation.ts';
import type { SpeechSetupReason, SpeechSetupScope } from '@core/speechsetup/protocols.ts';
import { requireSpeechSetup } from '@core/speechsetup/service.ts';
import { isSpeechSetupResolved } from '@core/speechsetup/modelSelector.ts';
import { dismissPersistentNotificationsByDedupeKey, showPersistentNotification } from '@core/ui/notifications/notifications.ts';
import type { NotificationButton } from '@core/ui/notifications/types.ts';
import { isNotificationDismissed } from '@core/ui/notifications/service.ts';

const SPEECH_NOTIFICATION_PREFIX = 'speech-setup:';

const notifyObservedSpeechOutcome = async (message: string, operationId: string, reason: SpeechSetupReason | null, selector: string, scope: SpeechSetupScope, restrictedMessage = ''): Promise<void> => {
    const auth = resolveKernelService('core.auth');
    const userId = auth.getCurrentUser()?.id;
    if (userId === undefined) return;
    const permissionController = new AbortController();
    const releaseLogoutObserver = auth.onLogout(() => permissionController.abort());
    let permissions: WebuiPermissionsSnapshot;
    try {
        permissions = await loadWebuiPermissionsSnapshot({ signal: permissionController.signal });
    } catch (error) {
        if (permissionController.signal.aborted) return;
        throw error;
    } finally {
        releaseLogoutObserver();
    }
    if (permissionController.signal.aborted || auth.getCurrentUser()?.id !== userId) return;
    const granted = permissions.grantedActions;
    const navigate = (route: string): void => {
        getLocation().hash = route;
    };
    const pluginReason = reason === 'no_stt_plugin' || reason === 'no_tts_plugin' || reason === 'backend_not_installed' || reason === 'plugin_disabled';
    const liveSetup = granted.has('PLUGIN_READ') && granted.has('MODEL_READ') ? requireSpeechSetup().snapshot(scope) : null;
    const modelDownloadAvailable = liveSetup === null || !liveSetup.fresh || liveSetup.candidates.some((candidate) => candidate.modelsDownloadable);
    const buttons: NotificationButton[] = [];
    if (scope === 'media' && granted.has('CONFIG_PATCH')) buttons.push({ text: i18n.t('speechSetup.openSettings'), variant: 'neutral', action: () => navigate(buildSpeechModelSettingsRoute()) });
    else if (pluginReason && granted.has('PLUGIN_ADMIN')) buttons.push({ text: i18n.t('speechSetup.openPlugins'), variant: 'neutral', action: () => navigate('#plugins') });
    else if (reason === 'model_disabled' && granted.has('MODEL_ADMIN')) buttons.push({ text: i18n.t('speechSetup.openModels'), variant: 'neutral', action: () => navigate('#models') });
    else if (granted.has('MODEL_ADMIN') && modelDownloadAvailable) buttons.push({ text: i18n.t('models.actions.addModel'), variant: 'neutral', action: () => navigate(buildSpeechAddModelRoute(requireSpeechSetup().snapshot(scope).candidates)) });
    else if (granted.has('PLUGIN_ADMIN')) buttons.push({ text: i18n.t('speechSetup.openPlugins'), variant: 'neutral', action: () => navigate('#plugins') });
    const dedupeKey = `${SPEECH_NOTIFICATION_PREFIX}${String(userId)}:${operationId}`;
    const cleanup = new CleanupStack({ logError: (message, error) => errorHandler.warn('SpeechSetup', message, error) });
    const notification = showPersistentNotification({ message: buttons.length > 0 ? message : restrictedMessage || `${message} ${speechSetupAskAdministratorMessage(scope)}`, type: 'warning', buttons, dedupeKey, onClose: () => cleanup.dispose() });
    if (notification === null || notification.dataset['speechSetupScope'] !== undefined) {
        cleanup.dispose();
        return;
    }
    if (reason !== null) notification.dataset['speechSetupReason'] = reason;
    notification.dataset['speechSetupSelector'] = selector;
    notification.dataset['speechSetupScope'] = scope;
    cleanup.add(
        auth.onLogout(() => {
            cleanup.dispose();
            dismissPersistentNotificationsByDedupeKey(dedupeKey);
        })
    );
    if (!granted.has('PLUGIN_READ') || !granted.has('MODEL_READ')) return;
    const service = requireSpeechSetup();
    const isCurrent = (): boolean => notification.isConnected && !isNotificationDismissed(notification) && auth.getCurrentUser()?.id === userId;
    const reconcile = (): void => {
        if (isCurrent() && isSpeechSetupResolved(service.snapshot(scope), reason ?? 'no_model_installed', selector)) dismissPersistentNotificationsByDedupeKey(dedupeKey);
    };
    cleanup.add(service.subscribe(reconcile));
    void service
        .ensureReady()
        .then(reconcile)
        .catch((error) => {
            if (isCurrent()) errorHandler.warn('SpeechSetup', 'Speech setup status could not be loaded', ensureError(error));
        });
};

export { notifyObservedSpeechOutcome };
