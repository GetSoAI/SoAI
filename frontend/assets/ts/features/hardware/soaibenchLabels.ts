/* SoAI - Hardware feature SoAI Bench labels [frontend/assets/ts/features/hardware/soaibenchLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatSentenceLabelFromId } from '@core/primitives/text.ts';

const notAvailable = (): string => i18n.t('common.notAvailableShort');

const formatUnexpectedSoAIBenchIdentifierLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    if (/^[a-z0-9_]+$/i.test(value)) {
        return formatSentenceLabelFromId(value);
    }
    return value;
};

const resolveSoAIBenchProfileLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    switch (value) {
        case 'standard':
            return i18n.t('hardware.modals.soaibenchHistory.profiles.standard');
        case 'stress':
            return i18n.t('hardware.modals.soaibenchHistory.profiles.stress');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

const resolveSoAIBenchStatusLabel = (value: string | null): string => {
    if (!value) {
        return notAvailable();
    }
    switch (value) {
        case 'running':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.running');
        case 'completed':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.completed');
        case 'unstable':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.unstable');
        case 'failed':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.failed');
        case 'cancelled':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.cancelled');
        case 'stopped':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.stopped');
        case 'unsupported':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.unsupported');
        case 'indeterminate':
            return i18n.t('hardware.modals.soaibenchHistory.statuses.indeterminate');
        default:
            return formatUnexpectedSoAIBenchIdentifierLabel(value);
    }
};

export { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchStatusLabel };
