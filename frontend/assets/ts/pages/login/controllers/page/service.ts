/* SoAI - Login page service [frontend/assets/ts/pages/login/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBranding } from '@core/branding/public.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { getLocation, getRequestAnimationFrame } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { setControlDisabledStateForEach } from '@core/ui/controls/disabledState.ts';
import { setSecretInputVisibility } from '@core/ui/secretInput.ts';
import type { LoginPageHost } from '@pages/login/controllers/page/contracts.ts';
import { requireLoginUi } from '@pages/login/dom.ts';
import { isLoginResult } from '@pages/login/guards/guards.ts';
import type { AuthService, LoginUiRefs } from '@pages/login/types.ts';

const resolveAuthService = (page: LoginPageHost): AuthService | null => {
    return page.auth && typeof page.auth === 'object' ? page.auth : null;
};

interface LoginCooldownState {
    remainingSeconds: number;
    intervalId: number | null;
}

const loginCooldownStates = new WeakMap<LoginPageHost, LoginCooldownState>();

const scheduleLoginCooldownTick = (page: LoginPageHost, ui: LoginUiRefs): void => {
    const cooldownState = loginCooldownStates.get(page);
    if (!cooldownState) {
        return;
    }
    cooldownState.intervalId = page.pageResources.setTimeout((): void => {
        const activeState = loginCooldownStates.get(page);
        if (!activeState) {
            return;
        }
        const nextRemaining = Math.max(0, activeState.remainingSeconds - 1);
        activeState.remainingSeconds = nextRemaining;
        if (nextRemaining <= 0) {
            clearLoginCooldown(page);
            if (!page.isLoading) {
                setLoginDisabled(ui, false);
                updateLoginStatusMessage(page, ui);
            }
            return;
        }
        updateLoginStatusMessage(page, ui, i18n.t('login.errors.rateLimitedCountdown', { seconds: nextRemaining }));
        scheduleLoginCooldownTick(page, ui);
    }, 1000);
    if (cooldownState.intervalId === null) {
        throw new Error('Failed to schedule login cooldown timer');
    }
};

const clearLoginCooldown = (page: LoginPageHost): void => {
    const cooldownState = loginCooldownStates.get(page);
    if (!cooldownState) {
        return;
    }
    if (cooldownState.intervalId !== null) {
        page.pageResources.clearTimer(cooldownState.intervalId);
    }
    loginCooldownStates.delete(page);
};

const getLoginCooldownRemainingSeconds = (page: LoginPageHost): number => {
    const cooldownState = loginCooldownStates.get(page);
    if (!cooldownState) {
        return 0;
    }
    return Math.max(0, Math.floor(cooldownState.remainingSeconds));
};

const isLoginCooldownActive = (page: LoginPageHost): boolean => {
    return getLoginCooldownRemainingSeconds(page) > 0;
};

const syncLoginCooldownUiState = (page: LoginPageHost, ui: LoginUiRefs): void => {
    if (isLoginCooldownActive(page)) {
        setLoginDisabled(ui, true);
        return;
    }
    if (!page.isLoading) {
        setLoginDisabled(ui, false);
    }
};

const startLoginCooldown = (page: LoginPageHost, ui: LoginUiRefs, retryAfterSeconds: number): void => {
    const normalizedSeconds = Math.max(0, Math.floor(retryAfterSeconds));
    clearLoginCooldown(page);
    if (normalizedSeconds <= 0) {
        syncLoginCooldownUiState(page, ui);
        return;
    }
    const cooldownState: LoginCooldownState = {
        remainingSeconds: normalizedSeconds,
        intervalId: null
    };
    loginCooldownStates.set(page, cooldownState);
    setLoginDisabled(ui, true);
    updateLoginStatusMessage(page, ui, i18n.t('login.errors.rateLimitedCountdown', { seconds: normalizedSeconds }));
    scheduleLoginCooldownTick(page, ui);
};

const redirectLoginToWizardIfNeeded = async (page: LoginPageHost): Promise<boolean> => {
    const auth = resolveAuthService(page);
    if (auth?.checkWizardStatus && isFunction(auth.checkWizardStatus)) {
        const needsWizard = await auth.checkWizardStatus();
        if (needsWizard) {
            const locationRef = getLocation();
            locationRef.replace(`${locationRef.origin}${locationRef.pathname}#${AUTH_ROUTE_WIZARD}`);
            return true;
        }
    }
    return false;
};

const resolveLoginUiForPage = (page: LoginPageHost, existingUi: LoginUiRefs | null): LoginUiRefs => {
    if (existingUi) {
        return existingUi;
    }
    return requireLoginUi(page);
};

const setLoginDisabled = (ui: LoginUiRefs, disabled: boolean): void => {
    const { loginButton, username, password } = ui;
    setControlDisabledStateForEach([loginButton, username, password], disabled);
};

const updateLoginStatusMessage = (page: LoginPageHost, ui: LoginUiRefs, message = '', type: 'error' | 'success' = 'error'): void => {
    page.pageDom.updateText(ui.loginError, message);
    page.pageDom.removeClass(ui.loginError, ['login-success', 'form-disclaimer', 'form-disclaimer-error', 'u-hidden']);
    if (message) {
        page.pageDom.addClass(ui.loginError, type === 'success' ? 'login-success' : ['form-disclaimer', 'form-disclaimer-error']);
    } else {
        page.pageDom.addClass(ui.loginError, ['form-disclaimer', 'form-disclaimer-error', 'u-hidden']);
    }
    if (message) {
        scrollElementIntoView(ui.loginError, { behavior: 'smooth', block: 'nearest' });
    }
};

const setLoginLoading = (page: LoginPageHost, ui: LoginUiRefs, loading: boolean, idleText: string): void => {
    page.isLoading = loading;
    const stateService = page.stateManager;
    const disableTargets: Element[] = [ui.username, ui.password];
    stateService?.setButtonLoading(ui.loginButton, loading, {
        textTarget: ui.loginButtonText,
        loadingText: i18n.t('login.signInButton'),
        idleText,
        disableTargets
    });
    setLoginDisabled(ui, loading);
};

const submitLoginForm = async (page: LoginPageHost, ui: LoginUiRefs, event: Event): Promise<void> => {
    event.preventDefault();
    if (page.isLoading || isLoginCooldownActive(page)) {
        return;
    }

    const username = readTrimmedInputValue(ui.username);
    const password = ui.password.value;

    if (!username) {
        updateLoginStatusMessage(page, ui, i18n.t('login.errors.enterUsername'));
        ui.username.focus();
        return;
    }
    if (!password) {
        updateLoginStatusMessage(page, ui, i18n.t('login.errors.enterPassword'));
        ui.password.focus();
        return;
    }

    setLoginLoading(page, ui, true, i18n.t('login.signInButton'));
    const auth = resolveAuthService(page);
    let isAuthenticated = false;

    await page.streaming.runTask(
        'login.submit',
        async () => {
            const result = auth?.login ? await auth.login(username, password) : null;
            if (result && isLoginResult(result) && result.status === 'authenticated') {
                isAuthenticated = true;
                clearLoginCooldown(page);
                updateLoginStatusMessage(page, ui);
                return;
            }
            const retryAfterSeconds = result && isLoginResult(result) && result.status === 'rejected' ? result.retryAfterSeconds : undefined;
            const errorMessage = result && isLoginResult(result) && isString(result.error) && result.error ? result.error : i18n.t('login.errors.loginFailed');
            updateLoginStatusMessage(page, ui, errorMessage);
            if (typeof retryAfterSeconds === 'number' && Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
                startLoginCooldown(page, ui, retryAfterSeconds);
            } else {
                clearLoginCooldown(page);
            }
            ui.password.select();
        },
        {
            displayName: i18n.t('login.submit'),
            onError: () => {
                updateLoginStatusMessage(page, ui, i18n.t('login.errors.tryAgain'));
            },
            onFinally: () => {
                setLoginLoading(page, ui, false, isAuthenticated ? i18n.t('login.signInSuccess') : i18n.t('login.signInButton'));
                syncLoginCooldownUiState(page, ui);
            },
            rethrow: false
        }
    );
};

const initializeLoginUi = async (page: LoginPageHost, ui: LoginUiRefs): Promise<void> => {
    clearLoginCooldown(page);
    setLoginDisabled(ui, true);
    getBranding().updateLogoElement(ui.logo, 'ui');

    ui.password.classList.add('secret-input');
    setSecretInputVisibility(ui.password, false);

    const session = page.storage?.getSession?.();
    const sessionUsername = isObject(session) ? session['username'] : null;
    if (isString(sessionUsername) && sessionUsername && ui.username) {
        page.pageElements.setValue(ui.username, sessionUsername, { attribute: 'value' });
    }

    const raf = getRequestAnimationFrame();
    raf(() => {
        const focusTarget = ui.username.value ? ui.password : ui.username;
        focusTarget.focus();
    });

    setLoginDisabled(ui, false);
};

export { clearLoginCooldown, initializeLoginUi, isLoginCooldownActive, redirectLoginToWizardIfNeeded, resolveLoginUiForPage, submitLoginForm, updateLoginStatusMessage };
