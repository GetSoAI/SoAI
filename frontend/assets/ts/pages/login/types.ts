/* SoAI - Login page public contracts [frontend/assets/ts/pages/login/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LoginResult } from '@core/auth/public.ts';

export interface LoginUiRefs {
    root: HTMLElement;
    logo: HTMLImageElement;
    form: HTMLFormElement;
    username: HTMLInputElement;
    password: HTMLInputElement;
    loginButton: HTMLButtonElement;
    loginButtonText: HTMLElement;
    loginError: HTMLElement;
}

export interface AuthService {
    checkWizardStatus?: () => Promise<boolean>;
    login?: (username: string, password: string) => Promise<LoginResult>;
}

export type { LoginResult };
