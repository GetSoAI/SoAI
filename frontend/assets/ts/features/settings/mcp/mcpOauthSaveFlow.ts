/* SoAI - MCP OAuth server save flow [frontend/assets/ts/features/settings/mcp/mcpOauthSaveFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpOauthStartResponse, McpServer } from '@core/mcp/contracts.ts';
import { setStatusSurface } from '@core/ui/statusSurface.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import { parseMcpOauthStartResult, resolveMcpOauthFailureMessage, type McpOauthStartResult } from '@features/settings/mcp/mcpOauthState.ts';
import { buildPartialCreateOrUpdateFailure, formatSaveResult, reloadAfterPartialSaveFailure, requireReloadedPersistedServer, type McpServerModalSaveDependencies, type McpServerModalSaveResult } from '@features/settings/mcp/mcpServerModalSaveController.ts';
import { openOauthPopupAndWait, type OAuthPopupResult } from '@features/settings/oauthPopupFlowController.ts';

type McpOauthSaveFlowArguments = {
    dependencies: McpServerModalSaveDependencies;
    serverId: string;
    persistedServer: McpServer;
    reloadAfterSave: boolean;
    changedBeforeOauth: boolean;
    startFailureLogMessage: string;
    popupFailureLogMessage: string;
};

const completeOauthServerSave = async (inputArguments: McpOauthSaveFlowArguments): Promise<McpServerModalSaveResult> => {
    const resolvePersistedServer = (changed: boolean): McpServer => {
        if (!changed) {
            return inputArguments.persistedServer;
        }
        return requireReloadedPersistedServer(inputArguments.dependencies, inputArguments.serverId);
    };
    let startResponse: McpOauthStartResponse;
    try {
        startResponse = await inputArguments.dependencies.host.services.api.mcp.oauth.start(inputArguments.serverId);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('SettingsPage', inputArguments.startFailureLogMessage, runtimeError);
        const reloadSucceeded = await reloadAfterPartialSaveFailure(inputArguments.dependencies, inputArguments.reloadAfterSave, inputArguments.changedBeforeOauth);
        const persistedServer = reloadSucceeded ? resolvePersistedServer(inputArguments.changedBeforeOauth) : inputArguments.persistedServer;
        return buildPartialCreateOrUpdateFailure(inputArguments.dependencies, persistedServer, {
            changed: inputArguments.changedBeforeOauth,
            shouldReload: inputArguments.changedBeforeOauth && !reloadSucceeded
        });
    }
    const startResult: McpOauthStartResult = parseMcpOauthStartResult(startResponse);

    if (startResult.kind === 'not_required') {
        const changedAfterOauthCheck = true;
        inputArguments.dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthNotRequired'), 'info');
        let persistedServer = inputArguments.persistedServer;
        let reloadSucceeded = false;
        if (inputArguments.reloadAfterSave) {
            reloadSucceeded = await inputArguments.dependencies.reload();
            if (reloadSucceeded) {
                persistedServer = resolvePersistedServer(changedAfterOauthCheck);
            }
        }
        return formatSaveResult({
            persistedServer,
            finalMode: 'edit',
            shouldClose: !inputArguments.reloadAfterSave || reloadSucceeded,
            shouldReload: !inputArguments.reloadAfterSave || !reloadSucceeded,
            changed: changedAfterOauthCheck
        });
    }
    if (startResult.kind === 'manual_required') {
        inputArguments.dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthManualRequired'), 'warning');
        setVisibilityState(inputArguments.dependencies.oauthManualSection, true, { mode: 'hiddenAttribute' });
        setStatusSurface({
            surface: inputArguments.dependencies.summary,
            message: i18n.t('settings.mcp.notifications.oauthManualRequired')
        });
        inputArguments.dependencies.oauthClientIdInput.focus();
        const reloadSucceeded = await reloadAfterPartialSaveFailure(inputArguments.dependencies, inputArguments.reloadAfterSave, inputArguments.changedBeforeOauth);
        const persistedServer = reloadSucceeded ? resolvePersistedServer(inputArguments.changedBeforeOauth) : inputArguments.persistedServer;
        return formatSaveResult({
            persistedServer,
            finalMode: 'edit',
            shouldClose: false,
            shouldReload: inputArguments.changedBeforeOauth && !reloadSucceeded,
            changed: inputArguments.changedBeforeOauth
        });
    }
    if (startResult.kind === 'redirect') {
        const changedAfterOauthStart = true;
        setStatusSurface({
            surface: inputArguments.dependencies.summary,
            message: i18n.t('settings.mcp.notifications.oauthPopupPending')
        });
        let popupResult: OAuthPopupResult;
        try {
            popupResult = await openOauthPopupAndWait({
                redirectUrl: startResult.redirectUrl,
                pollStatus: async () => (await inputArguments.dependencies.host.services.api.mcp.oauth.status(inputArguments.serverId)).oauthStatus,
                logContext: 'McpServerEffects',
                startFailureMessage: i18n.t('settings.mcp.notifications.oauthFailed'),
                statusFailureMessage: i18n.t('settings.mcp.notifications.oauthFailed')
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('SettingsPage', inputArguments.popupFailureLogMessage, runtimeError);
            const reloadSucceeded = await reloadAfterPartialSaveFailure(inputArguments.dependencies, inputArguments.reloadAfterSave, changedAfterOauthStart);
            const persistedServer = reloadSucceeded ? resolvePersistedServer(changedAfterOauthStart) : inputArguments.persistedServer;
            return buildPartialCreateOrUpdateFailure(inputArguments.dependencies, persistedServer, {
                changed: changedAfterOauthStart,
                shouldReload: !reloadSucceeded
            });
        }
        if (popupResult.ok) {
            inputArguments.dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthAuthorized'), 'success');
            let persistedServer = inputArguments.persistedServer;
            let reloadSucceeded = false;
            if (inputArguments.reloadAfterSave) {
                reloadSucceeded = await inputArguments.dependencies.reload();
                if (reloadSucceeded) {
                    persistedServer = resolvePersistedServer(true);
                }
            }
            return formatSaveResult({
                persistedServer,
                finalMode: 'edit',
                shouldClose: !inputArguments.reloadAfterSave || reloadSucceeded,
                shouldReload: !inputArguments.reloadAfterSave || !reloadSucceeded,
                changed: true
            });
        }
        const failureMessage = resolveMcpOauthFailureMessage(popupResult.oauthStatus);
        inputArguments.dependencies.host.execution.feedback.show(failureMessage, 'error');
        setStatusSurface({
            surface: inputArguments.dependencies.summary,
            message: failureMessage
        });
        const reloadSucceeded = await reloadAfterPartialSaveFailure(inputArguments.dependencies, inputArguments.reloadAfterSave, changedAfterOauthStart);
        const persistedServer = reloadSucceeded ? resolvePersistedServer(changedAfterOauthStart) : inputArguments.persistedServer;
        return formatSaveResult({
            persistedServer,
            finalMode: 'edit',
            shouldClose: false,
            shouldReload: !reloadSucceeded,
            changed: changedAfterOauthStart
        });
    }
    if (startResult.diagnostic) {
        errorHandler.warn('SettingsPage', inputArguments.popupFailureLogMessage, { diagnostic: startResult.diagnostic });
    }
    const oauthFailureMessage = i18n.t('settings.mcp.notifications.oauthFailed');
    inputArguments.dependencies.host.execution.feedback.show(oauthFailureMessage, 'error');
    setStatusSurface({
        surface: inputArguments.dependencies.summary,
        message: oauthFailureMessage
    });
    const reloadSucceeded = await reloadAfterPartialSaveFailure(inputArguments.dependencies, inputArguments.reloadAfterSave, inputArguments.changedBeforeOauth);
    const persistedServer = reloadSucceeded ? resolvePersistedServer(inputArguments.changedBeforeOauth) : inputArguments.persistedServer;
    return formatSaveResult({
        persistedServer,
        finalMode: 'edit',
        shouldClose: false,
        shouldReload: inputArguments.changedBeforeOauth && !reloadSucceeded,
        changed: inputArguments.changedBeforeOauth
    });
};

export { completeOauthServerSave };
export type { McpOauthSaveFlowArguments };
