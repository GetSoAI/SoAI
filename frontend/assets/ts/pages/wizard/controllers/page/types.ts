/* SoAI - Wizard page control layer public contracts [frontend/assets/ts/pages/wizard/controllers/page/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { WizardCompletionResult, WizardStatus } from '@core/auth/public.ts';

interface WizardPageEffectsHost {
    getAuth: () => {
        getWizardStatusSnapshot?: () => WizardStatus | null;
        checkWizardStatus?: () => Promise<boolean>;
        completeWizard?: (username: string, password: string) => Promise<WizardCompletionResult>;
    } | null;
    getStorage: () => {
        setWizardCompleted?: () => Promise<void>;
        get?: (key: string, defaultValue?: JsonValue) => JsonValue;
        set?: (key: string, value: JsonValue) => void;
        isWizardCompletionPending?: () => boolean;
    } | null;
    isAuthenticated: () => boolean;
    getWizardStatus: () => WizardStatus | null;
    setWizardStatus: (status: WizardStatus | null) => void;
    getWizardVisible: () => boolean | null;
    setWizardVisible: (visible: boolean | null) => void;
    logWarn: (message: string, error?: Error | undefined) => void;
}

export type { WizardPageEffectsHost };
