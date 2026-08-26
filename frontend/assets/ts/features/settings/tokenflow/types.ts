/* SoAI - Settings feature tokenflow contracts [frontend/assets/ts/features/settings/tokenflow/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalDefinition } from '@core/modals/modalPresenter.ts';

type SettingsTokenExpiryChoice = 'back' | 'never' | '90days';

type SettingsTokenModalText = {
    title: string;
    message: string;
    description: string;
};

type SettingsTokenLabelModalConfig = {
    modalId: string;
    contextLabel: string;
    text: SettingsTokenModalText;
    placeholder: string | null;
    required: boolean;
};

type SettingsTokenExpiryModalConfig = {
    modalId: string;
    contextLabel: string;
    title: string;
    help: string;
    description: string;
    neverLabel: string;
    ninetyDaysLabel: string;
};

type SettingsTokenSecretModalConfig = {
    modalId: string;
    contextLabel: string;
    title: string;
    message: string;
    messageEmphasis: string;
    copyLabel: string;
};

type SettingsTokenModalDefinitionSet = {
    label: ModalDefinition;
    expiry: ModalDefinition;
    secret: ModalDefinition;
};

type SettingsTokenStatus = 'active' | 'revoked' | 'expired';

type SettingsTokenStatusLabels = Record<SettingsTokenStatus, string>;

export type { SettingsTokenExpiryChoice, SettingsTokenExpiryModalConfig, SettingsTokenLabelModalConfig, SettingsTokenModalDefinitionSet, SettingsTokenModalText, SettingsTokenSecretModalConfig, SettingsTokenStatus, SettingsTokenStatusLabels };
