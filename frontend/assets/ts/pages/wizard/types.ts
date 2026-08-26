/* SoAI - Wizard page public contracts [frontend/assets/ts/pages/wizard/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { WizardState } from '@features/wizard/public.ts';

export type ProductAccessFlow = NonNullable<WizardStatusResponse['selectedProductAccessFlow']>;

export interface WizardUi {
    root: HTMLElement;
    logo: HTMLImageElement;
    content: HTMLElement;
    progressFill: HTMLElement;
    progressText: HTMLElement;
    navBackButton: HTMLButtonElement;
    navNextButton: HTMLButtonElement;
}

export interface WizardAccountUi {
    form: HTMLFormElement;
    errorBox: HTMLElement;
}

export interface WizardViewContext {
    getIconSync: (name: IconName, options: { width: number; height: number }) => TrustedHtml;
    sanitizer: {
        html: (value: string) => string;
        attribute: (value: string) => string;
    };
    state: WizardState;
    currentLanguage: string;
    languageOptions: Array<{ value: string; label: string }>;
}
