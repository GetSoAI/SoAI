/* SoAI - Automation page configuration limits controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationLimitsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { readBoundedPositiveIntegerTextOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { HARD_MAX_RUN_MINUTES } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';

interface LimitsUi {
    maxRunMinutesInput: HTMLInputElement;
}

class AutomationConfigurationLimitsController {
    readonly #ui: LimitsUi;

    constructor(ui: LimitsUi) {
        this.#ui = ui;
    }

    setValues(values: { maxRunMinutes: number }): void {
        this.#ui.maxRunMinutesInput.value = String(values.maxRunMinutes);
    }

    getSnapshotKey(): { maxRunMinutes: number | null } {
        return {
            maxRunMinutes: readBoundedPositiveIntegerTextOrNullValue(this.#ui.maxRunMinutesInput.value, HARD_MAX_RUN_MINUTES)
        };
    }

    readAndValidate(): { maxRunMinutes: number } | null {
        const maxRunMinutes = readBoundedPositiveIntegerTextOrNullValue(this.#ui.maxRunMinutesInput.value, HARD_MAX_RUN_MINUTES);
        if (maxRunMinutes === null) {
            return null;
        }
        return { maxRunMinutes: maxRunMinutes };
    }

    getValidationError(): string | null {
        const maxRunMinutes = readBoundedPositiveIntegerTextOrNullValue(this.#ui.maxRunMinutesInput.value, HARD_MAX_RUN_MINUTES);
        if (maxRunMinutes === null) {
            return i18n.t('automation.modal.validation.maxRunMinutesInvalid');
        }
        return null;
    }
}

export { AutomationConfigurationLimitsController };
