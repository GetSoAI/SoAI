/* SoAI - Automation page configuration turns controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseNonNegativeIntegerFromStringOrNull } from '@core/dom/attributes.ts';
import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isString } from '@core/typeGuards.ts';
import { AUTOMATION_ACTION_REMOVE_TURN } from '@features/automation/public.ts';
import { HARD_MAX_TURN_CHARS, HARD_MAX_TURNS } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import { queryAutomationTurnTextareas } from '@pages/automation/dom.ts';

const AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT = 'automation:configuration:turns-updated';

interface TurnsControllerDependencies {
    turnsList: HTMLElement;
    turnsCharCounter: HTMLElement;
}

const normalizeTurns = (turns: readonly string[]): string[] => {
    const normalized: string[] = [];
    for (const turn of turns) {
        const value = isString(turn) ? turn.trim() : '';
        normalized.push(value);
    }
    return normalized;
};

const applyCharCounterState = (counter: HTMLElement, used: number): void => {
    counter.textContent = i18n.t('automation.modal.counters.turnChars', { used });
    const ratio = used / HARD_MAX_TURN_CHARS;
    const isOver = used > HARD_MAX_TURN_CHARS;
    const isCritical = !isOver && ratio >= 0.99;
    const isWarning = !isOver && !isCritical && ratio >= 0.9;
    counter.classList.toggle('is-warning', isWarning);
    counter.classList.toggle('is-critical', isCritical);
    counter.classList.toggle('is-over', isOver);
};

const createTurnConnector = (documentRef: Document): HTMLElement => {
    const connector = documentRef.createElement('div');
    connector.className = 'automation-turn-connector';
    connector.setAttribute('aria-hidden', 'true');
    return connector;
};

const resolveTurnPlaceholder = (turnCount: number, index: number): string => {
    if (turnCount <= 1) {
        return i18n.t('automation.modal.placeholders.turn');
    }
    return i18n.t('automation.modal.placeholders.turnIndexed', { index: String(index + 1) });
};

class AutomationConfigurationTurnsController {
    readonly #dependencies: TurnsControllerDependencies;

    constructor(dependencies: TurnsControllerDependencies) {
        this.#dependencies = dependencies;
    }

    getSnapshotKey(): { turns: string[] } {
        return {
            turns: this.readNormalizedTurns()
        };
    }

    readTurns(): string[] {
        const inputs = queryAutomationTurnTextareas(this.#dependencies.turnsList);
        const turns: string[] = [];
        for (const element of inputs) {
            turns.push(element.value);
        }
        return turns.length ? turns : [''];
    }

    readNormalizedTurns(): string[] {
        return normalizeTurns(this.readTurns());
    }

    refreshCounters(): void {
        const turnInputs = queryAutomationTurnTextareas(this.#dependencies.turnsList);
        const maxUsed = turnInputs.reduce((acc, textarea) => Math.max(acc, textarea.value.length), 0);
        applyCharCounterState(this.#dependencies.turnsCharCounter, maxUsed);
    }

    renderTurns(turns: readonly string[], render: { readOnly: boolean }): void {
        this.#dependencies.turnsList.replaceChildren();

        const removeLabel = i18n.t('common.delete');
        const assistantPlaceholder = i18n.t('automation.modal.placeholders.assistantTurn');
        const endMarkerText = i18n.t('automation.modal.placeholders.endOfAutomation');
        const visibleTurns = turns.length ? turns.slice() : [''];

        const maxUsed = visibleTurns.reduce((acc, turn) => Math.max(acc, turn.length), 0);
        applyCharCounterState(this.#dependencies.turnsCharCounter, maxUsed);

        visibleTurns.forEach((turn, index) => {
            const row = document.createElement('div');
            row.className = 'automation-turn-row';
            const fields = document.createElement('div');
            fields.className = 'automation-turn-fields';

            const textarea = document.createElement('textarea');
            textarea.className = 'form-input automation-turn-input';
            textarea.rows = 2;
            textarea.placeholder = resolveTurnPlaceholder(visibleTurns.length, index);
            textarea.value = turn;
            textarea.dataset['turnIndex'] = String(index);
            textarea.readOnly = render.readOnly;

            const assistant = document.createElement('textarea');
            assistant.className = 'form-input automation-turn-input automation-turn-assistant-input';
            assistant.rows = 2;
            assistant.placeholder = assistantPlaceholder;
            assistant.disabled = true;
            assistant.readOnly = true;
            assistant.tabIndex = -1;
            assistant.setAttribute('aria-disabled', 'true');

            const actions = document.createElement('div');
            actions.className = 'automation-turn-actions';

            if (!render.readOnly) {
                const removeButton = document.createElement('button');
                removeButton.type = 'button';
                removeButton.className = 'ui-button ui-variant-danger';
                removeButton.textContent = removeLabel;
                removeButton.dataset['action'] = AUTOMATION_ACTION_REMOVE_TURN;
                removeButton.dataset['turnIndex'] = String(index);
                removeButton.disabled = visibleTurns.length <= 1;
                actions.append(removeButton);
            }
            fields.append(textarea, createTurnConnector(document), assistant);
            if (index === visibleTurns.length - 1) {
                const endMarker = document.createElement('textarea');
                endMarker.className = 'form-input automation-turn-input automation-turn-end-input';
                endMarker.rows = 1;
                endMarker.value = endMarkerText;
                endMarker.disabled = true;
                endMarker.readOnly = true;
                endMarker.tabIndex = -1;
                endMarker.setAttribute('aria-disabled', 'true');
                endMarker.setAttribute('aria-label', endMarkerText);
                fields.append(createTurnConnector(document), endMarker);
            }
            row.append(fields, actions);
            this.#dependencies.turnsList.append(row);
        });

        this.#dependencies.turnsList.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, { bubbles: true }));
    }

    canAddTurn(): boolean {
        const turns = this.readTurns();
        return turns.length < HARD_MAX_TURNS;
    }

    addTurn(): void {
        const turns = this.readTurns();
        if (turns.length >= HARD_MAX_TURNS) {
            return;
        }
        turns.push('');
        this.renderTurns(turns, { readOnly: false });
    }

    removeTurn(indexCandidate: string | null): void {
        const index = indexCandidate === null ? null : parseNonNegativeIntegerFromStringOrNull(indexCandidate);
        if (index === null) {
            return;
        }
        const turns = this.readTurns();
        if (turns.length <= 1) {
            return;
        }
        const clamped = clampNumber(index, 0, turns.length - 1);
        const next = turns.filter((_turn, index) => index !== clamped);
        this.renderTurns(next.length ? next : [''], { readOnly: false });
    }
}

export { AutomationConfigurationTurnsController, AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT };
