/* SoAI - Automation page configuration turn UI controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationTurnUiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, AutomationConfigurationTurnsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts';

interface TurnUiDependencies {
    addTurnButton: HTMLButtonElement;
    turnsList: HTMLElement;
    turns: AutomationConfigurationTurnsController;
}

class AutomationConfigurationTurnUiController {
    readonly #dependencies: TurnUiDependencies;
    readonly #abort = new AbortController();
    #readOnly = false;

    constructor(dependencies: TurnUiDependencies) {
        this.#dependencies = dependencies;
        const { signal } = this.#abort;
        const handleTurnsUpdated = (): void => this.#handleTurnsUpdated();
        dependencies.turnsList.addEventListener(AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, handleTurnsUpdated, { signal });

        const handleTurnInput = (event: Event): void => this.#handleTurnInput(event);
        dependencies.turnsList.addEventListener('input', handleTurnInput, { signal });
    }

    destroy(): void {
        this.#abort.abort();
    }

    setReadOnly(readOnly: boolean): void {
        this.#readOnly = readOnly;
        if (readOnly) {
            this.#dependencies.addTurnButton.disabled = true;
            return;
        }
        this.#handleTurnsUpdated();
    }

    sync(): void {
        if (this.#readOnly) {
            this.#dependencies.addTurnButton.disabled = true;
            return;
        }
        this.#dependencies.turns.refreshCounters();
        this.#syncTurnActions();
    }

    #handleTurnsUpdated(): void {
        if (this.#readOnly) {
            return;
        }
        this.#dependencies.turns.refreshCounters();
        this.#syncTurnActions();
    }

    #handleTurnInput(event: Event): void {
        if (this.#readOnly) {
            return;
        }
        const target = event.target;
        if (!(target instanceof HTMLTextAreaElement) || !target.classList.contains('automation-turn-input')) {
            return;
        }
        this.#dependencies.turns.refreshCounters();
    }

    #syncTurnActions(): void {
        this.#dependencies.addTurnButton.disabled = this.#readOnly || !this.#dependencies.turns.canAddTurn();
    }
}

export { AutomationConfigurationTurnUiController };
