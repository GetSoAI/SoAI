/* SoAI - Wizard page public contracts [frontend/assets/ts/pages/wizard/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { WizardState } from '@features/wizard/public.ts';
import type { AiSetupViewModel } from '@pages/wizard/contracts/aisetup/types.ts';

export type ProductAccessFlow = NonNullable<WizardStatusResponse['selectedProductAccessFlow']>;

export interface WizardUi {
    root: HTMLElement;
    logo: HTMLImageElement;
    content: HTMLElement;
    progressFill: HTMLElement;
    progressText: HTMLElement;
    navBackButton: HTMLButtonElement;
    navNextButton: HTMLButtonElement;
    navFinishLaterButton: HTMLButtonElement;
    navSkipButton: HTMLButtonElement;
}

export interface WizardAccountUi {
    form: HTMLFormElement;
    errorBox: HTMLElement;
}

export interface WizardViewContext {
    getIconSync: (name: IconName, options: { width: number; height: number }) => TrustedHtml;
    sanitizer: Pick<SanitizerApi, 'html' | 'attribute' | 'text'>;
    state: WizardState;
    currentLanguage: string;
    languageOptions: Array<{ value: string; label: string; countryCode: string | null }>;
    aiSetup: AiSetupViewModel | null;
}
