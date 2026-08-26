/* SoAI - Model test modal state [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatMillisecondsAsSecondsUnit } from '@core/primitives/duration.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { TEST_BUTTON_TOKENS } from '@features/modeldetail/modals/testmodalmanager/constants.ts';
import type { TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';
import type { TestModalState } from '@features/modeldetail/modals/TestModalManagerTypes.ts';

export const createInitialState = (): TestModalState => {
    return {
        mode: null,
        active: false,
        completed: false,
        hasPluginError: false,
        errorMessage: null,
        logStartedAt: null,
        abortController: null,
        logEntries: [],
        pendingLogEntries: [],
        logFlushTimerId: null,
        logStreamCallback: null,
        logStreamHandle: null,
        logStreamPluginName: null,
        logLineLimit: 200,
        elapsedStartTime: null,
        elapsedTimerId: null,
        currentRequest: null,
        logsCollapseController: null
    };
};

export const resetSession = (context: TestModalRuntimeContext): void => {
    context.state.mode = null;
    context.state.active = false;
    context.state.completed = false;
    context.state.hasPluginError = false;
    context.state.errorMessage = null;
    context.state.logStartedAt = null;
    context.state.abortController?.abort();
    context.state.abortController = null;
    clearElapsedTimer(context);

    TEST_BUTTON_TOKENS.forEach((token) => {
        context.host.view.updateProperty(context.host.view.optionalUI(modalUiSelector(context.modalId, token), context.modalRoot), 'disabled', false);
    });
};

export const setElapsedSpinnerVisible = (context: TestModalRuntimeContext, visible: boolean): void => {
    const spinner = context.host.view.optionalUI(modalUiSelector(context.modalId, 'elapsed-spinner'), context.modalRoot);
    if (spinner) {
        context.host.view.toggleClassName(spinner, 'u-hidden', !visible);
    }
};

export const setElapsedVisible = (context: TestModalRuntimeContext, visible: boolean): void => {
    const element = context.host.view.optionalUI(modalUiSelector(context.modalId, 'timing-row'), context.modalRoot);
    if (element) {
        context.host.view.toggleClassName(element, 'u-hidden', !visible);
    }
};

export const updateElapsedDisplay = (context: TestModalRuntimeContext, milliseconds: number): void => {
    const element = context.host.view.optionalUI(modalUiSelector(context.modalId, 'elapsed-time'), context.modalRoot);
    if (element) {
        context.host.view.updateText(element, formatMillisecondsAsSecondsUnit(milliseconds, 1));
    }
};

export const refreshElapsedDisplay = (context: TestModalRuntimeContext): void => {
    if (context.state.elapsedStartTime) {
        updateElapsedDisplay(context, Date.now() - context.state.elapsedStartTime);
    }
};

export const clearElapsedTimer = (context: TestModalRuntimeContext): void => {
    if (context.state.elapsedTimerId) {
        context.host.view.clearTimer(context.state.elapsedTimerId);
        context.state.elapsedTimerId = null;
    }
};

export const updateResultMessage = (context: TestModalRuntimeContext, message: string): void => {
    const badge = context.host.view.optionalUI(modalUiSelector(context.modalId, 'result-badge'), context.modalRoot);
    const text = context.host.view.optionalUI(modalUiSelector(context.modalId, 'result-text'), context.modalRoot);

    if (badge) {
        context.host.view.updateProperty(badge, 'className', 'model-test-result-text-only');
    }
    if (text) {
        context.host.view.updateText(
            text,
            context.host.view.sanitizeText(message || i18n.t('modelDetail.modal.test.ready'), {
                allowEmpty: true
            })
        );
    }
};
