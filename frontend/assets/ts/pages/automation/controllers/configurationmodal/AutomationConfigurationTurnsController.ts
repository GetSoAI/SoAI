/* SoAI - Automation page configuration turns controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { parseNonNegativeIntegerFromStringOrNull } from '@core/dom/attributes.ts';
import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { AUTOMATION_ACTION_REMOVE_TURN } from '@features/automation/public.ts';
import { HARD_MAX_TURN_CHARS, HARD_MAX_TURNS } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import { queryAutomationTurnTextareas } from '@pages/automation/dom.ts';

const AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT = 'automation:configuration:turns-updated';

interface TurnsControllerDependencies {
    addTurnButton: HTMLButtonElement;
    modalId: string;
    turnsList: HTMLElement;
    turnsCharCounter: HTMLElement;
}

interface TurnRow {
    row: HTMLElement;
    label: HTMLLabelElement;
    textarea: HTMLTextAreaElement;
    fields: HTMLElement;
    removeButton: HTMLButtonElement;
}

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

const refreshTurnCounters = (dependencies: TurnsControllerDependencies, rows: readonly TurnRow[]): void => {
    applyCharCounterState(
        dependencies.turnsCharCounter,
        rows.reduce((maxUsed, row) => Math.max(maxUsed, row.textarea.value.length), 0)
    );
};

const createDecorativeTextarea = (className: string, rows: number): HTMLTextAreaElement => {
    const textarea = document.createElement('textarea');
    textarea.className = `form-input automation-turn-input ${className}`;
    textarea.rows = rows;
    textarea.disabled = true;
    textarea.readOnly = true;
    textarea.tabIndex = -1;
    textarea.setAttribute('aria-hidden', 'true');
    return textarea;
};

const createTurnConnector = (): HTMLElement => {
    const connector = document.createElement('div');
    connector.className = 'automation-turn-connector';
    connector.setAttribute('aria-hidden', 'true');
    return connector;
};

class AutomationConfigurationTurnsController {
    readonly #dependencies: TurnsControllerDependencies;
    readonly #endMarker: HTMLElement;
    readonly #rows: TurnRow[] = [];
    readonly #abort = new AbortController();
    #nextRowId = 0;
    #readOnly = false;

    constructor(dependencies: TurnsControllerDependencies) {
        this.#dependencies = dependencies;
        const endMarker = createDecorativeTextarea('automation-turn-end-input', 1);
        endMarker.value = i18n.t('automation.modal.placeholders.endOfAutomation');
        const endMarkerGroup = document.createElement('div');
        endMarkerGroup.className = 'automation-turn-end';
        endMarkerGroup.setAttribute('aria-hidden', 'true');
        endMarkerGroup.append(createTurnConnector(), endMarker);
        this.#endMarker = endMarkerGroup;
        const handleTurnInput = (event: Event): void => {
            if (event.target instanceof HTMLTextAreaElement && event.target.classList.contains('automation-turn-input')) {
                refreshTurnCounters(this.#dependencies, this.#rows);
            }
        };
        dependencies.turnsList.addEventListener('input', handleTurnInput, { signal: this.#abort.signal });
    }

    readTurns(): string[] {
        return this.#rows.map((row) => row.textarea.value);
    }

    readNormalizedTurns(): string[] {
        return this.readTurns().map((turn) => turn.trim());
    }

    refreshCounters(): void {
        refreshTurnCounters(this.#dependencies, this.#rows);
    }

    canAddTurn(): boolean {
        return !this.#readOnly && this.#rows.length < HARD_MAX_TURNS;
    }

    listTextareas(): HTMLTextAreaElement[] {
        return queryAutomationTurnTextareas(this.#dependencies.turnsList);
    }

    renderTurns(turns: readonly string[]): void {
        this.#rows.splice(0, this.#rows.length);
        this.#dependencies.turnsList.replaceChildren();
        for (const turn of turns.length ? turns : ['']) {
            this.#appendRow(turn, false);
        }
        this.#syncRows();
    }

    setReadOnly(readOnly: boolean): void {
        this.#readOnly = readOnly;
        this.#syncRows();
    }

    destroy(): void {
        this.#abort.abort();
    }

    addTurn(): void {
        if (!this.canAddTurn()) {
            return;
        }
        const row = this.#appendRow('', true);
        this.#syncRows();
        row.textarea.focus();
    }

    removeTurn(indexCandidate: string | null): void {
        const index = indexCandidate === null ? null : parseNonNegativeIntegerFromStringOrNull(indexCandidate);
        if (this.#readOnly || index === null || this.#rows.length <= 1 || index >= this.#rows.length) {
            return;
        }
        const [removed] = this.#rows.splice(index, 1);
        if (removed) {
            delete removed.textarea.dataset['turnIndex'];
            removeWithPresence(removed.row);
        }
        this.#syncRows();
        const focusTarget = this.#rows[Math.min(index, this.#rows.length - 1)];
        focusTarget?.textarea.focus();
    }

    #appendRow(value: string, animate: boolean): TurnRow {
        this.#nextRowId += 1;
        const textareaId = `${this.#dependencies.modalId}-turn-${String(this.#nextRowId)}`;
        const row = document.createElement('div');
        row.className = 'automation-turn-row';
        row.setAttribute('role', 'listitem');
        row.dataset['presence'] = '';
        row.dataset['presenceAtomic'] = '';
        const fields = document.createElement('div');
        fields.className = 'automation-turn-fields';
        const label = document.createElement('label');
        label.className = 'automation-turn-label';
        label.htmlFor = textareaId;
        const textarea = document.createElement('textarea');
        textarea.id = textareaId;
        textarea.className = 'form-input automation-turn-input';
        textarea.rows = 2;
        textarea.placeholder = i18n.t('automation.modal.placeholders.turn');
        textarea.value = value;
        const error = document.createElement('p');
        error.id = `${textareaId}-error`;
        error.className = 'form-field-error u-hidden';
        error.setAttribute('aria-live', 'polite');
        const assistant = createDecorativeTextarea('automation-turn-assistant-input', 2);
        assistant.placeholder = i18n.t('automation.modal.placeholders.assistantTurn');
        fields.append(label, textarea, error, createTurnConnector(), assistant);
        const actions = document.createElement('div');
        actions.className = 'automation-turn-actions';
        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'ui-button ui-variant-danger';
        removeButton.textContent = i18n.t('common.delete');
        removeButton.dataset['action'] = AUTOMATION_ACTION_REMOVE_TURN;
        actions.append(removeButton);
        row.append(fields, actions);
        insertWithPresence(this.#dependencies.turnsList, row, null, animate);
        const turnRow: TurnRow = { row, label, textarea, fields, removeButton };
        this.#rows.push(turnRow);
        return turnRow;
    }

    #syncRows(): void {
        const lastIndex = this.#rows.length - 1;
        this.#rows.forEach((turnRow, index) => {
            const turnLabel = i18n.t('automation.modal.turns.label', { index: String(index + 1) });
            const removeLabel = i18n.t('automation.modal.turns.remove', { index: String(index + 1) });
            turnRow.label.textContent = turnLabel;
            turnRow.textarea.dataset['turnIndex'] = String(index);
            turnRow.textarea.readOnly = this.#readOnly;
            turnRow.removeButton.dataset['turnIndex'] = String(index);
            turnRow.removeButton.setAttribute('aria-label', removeLabel);
            setTooltipText(turnRow.removeButton, removeLabel);
            turnRow.removeButton.disabled = this.#rows.length <= 1;
            turnRow.removeButton.classList.toggle('u-hidden', this.#readOnly);
            if (index === lastIndex) {
                turnRow.fields.append(this.#endMarker);
            }
        });
        this.refreshCounters();
        this.#dependencies.addTurnButton.disabled = !this.canAddTurn();
        this.#dependencies.turnsList.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, { bubbles: true }));
    }
}

export { AutomationConfigurationTurnsController, AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT };
