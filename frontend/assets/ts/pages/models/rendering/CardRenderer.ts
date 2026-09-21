/* SoAI - Models page card renderer [frontend/assets/ts/pages/models/rendering/CardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, toTrustedUiHtml } from '@core/security/public.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { BaseCardRenderer } from '@core/ui/BaseCardRenderer.ts';
import type { ButtonConfig } from '@core/uiprimitives/public.ts';
import { MODELS_ACTION_DELETE, MODELS_ACTION_EDIT_MODEL, MODELS_ACTION_EDIT_PARAMETERS, MODELS_ACTION_EDIT_VIRTUAL, MODELS_ACTION_STOP_MODEL } from '@pages/models/actions.ts';
import { buildBadges, buildMetrics, buildModelTypeBadge, isModelDisabled, isModelNew, prepareCardData } from '@pages/models/rendering/cardrenderer/service.ts';
import { buildModelListMetrics, buildModelListStatus } from '@pages/models/rendering/cardrenderer/listRowDetailsWidget.ts';
import { buildModelListEnabledToggle } from '@pages/models/rendering/cardrenderer/listRowToggleWidget.ts';
import type { CardData, ModelCardHost, ModelCardRendererOptions } from '@pages/models/rendering/cardrenderer/types.ts';

const ACTIVE_STATUS_DEFAULT: readonly string[] = Object.freeze([]);

class ModelCardRenderer extends BaseCardRenderer<ModelData | null, CardData> {
    protected override host: ModelCardHost;
    activeStatuses: string[];

    constructor(options: ModelCardRendererOptions) {
        super({ host: options.host });
        this.host = options.host;
        const { activeStatuses = ACTIVE_STATUS_DEFAULT } = options;
        const validated = filterStringArrayValue(activeStatuses);
        this.activeStatuses = [...new Set(validated)];
    }

    override render(model: ModelData | null): Element | null {
        if (!model) return null;
        const data = prepareCardData(model, this.host);
        if (!data.cardId) return null;
        const content = this.buildContent(model, data);
        if (!content) return null;
        const disabled = isModelDisabled(model, data.status);
        const className = this.buildClassList(['model-card', model.type === 'virtual' ? 'virtual-model' : '', isModelNew(model, this.host) ? 'session-recent-card' : '', ...this.buildStatusClasses(data.statusClass)]);
        const statusLineClass = this.buildClassList(['model-status-line', ...this.buildStatusClasses(data.statusClass)]);
        const markup = this.cards.card({
            className,
            dataset: { model: this.host.presentation.sanitizeText(String(data.cardId)), 'model-enabled': disabled ? 'false' : 'true' },
            actions: this.buildActionButtons(model),
            children: content,
            statusLine: { className: statusLineClass }
        });
        return this.materialize(toTrustedUiHtml(markup));
    }

    renderListRow(model: ModelData | null): HTMLElement | null {
        if (!model) return null;
        const data = prepareCardData(model, this.host);
        if (!data.cardId) return null;
        const disabled = isModelDisabled(model, data.status);
        const pluginName = data.pluginName ?? '';
        const providerName = data.providerName ?? '';
        const originId = data.baseIdentifier || this.host.identity.getModelOriginId(model);
        const cleanId = this.host.identity.extractCleanModelId(originId ?? '');
        const title = this.host.identity.getModelDisplayName(model) || cleanId;
        const universalLabel = model.type === 'virtual' ? i18n.t('models.virtualModelLabel') : model.universalId || cleanId;
        const metrics = buildMetrics(model, providerName, this.host);
        const typeBadge = buildModelTypeBadge(model, this.host);
        const statusClasses = this.buildStatusClasses(data.statusClass);
        const className = this.buildClassList(['models-list-row', model.type === 'virtual' ? 'virtual-model' : '', disabled ? 'is-disabled' : '', isModelNew(model, this.host) ? 'session-recent-row' : '', ...statusClasses]);
        const actionButtons = this.buildListActionButtons(model);
        const statusContent = this.buildListStatusContent(model, metrics.statusLabel, metrics.statusBadgeClass);
        const providerFact = this.host.status.isExternalProviderModel(model) && providerName ? `<div class="ui-collection-list__facts"><span class="ui-collection-list__fact" data-metric-key="provider"><span class="ui-metric-label">${i18n.t('models.table.provider')}</span><span class="ui-metric-value">${this.host.presentation.sanitizeText(providerName)}</span></span></div>` : '';
        const markup = `
            <tr class="${className}" data-render-mode="list" data-action="${MODELS_ACTION_EDIT_PARAMETERS}" data-model="${this.host.presentation.sanitizeText(String(data.cardId))}" data-model-enabled="${disabled ? 'false' : 'true'}">
                <td class="models-list-cell models-list-cell-main">
                    <button type="button" class="models-list-open" data-action="${MODELS_ACTION_EDIT_PARAMETERS}" ${renderLabelAttributes(title)}>
                        <span class="models-list-title-row">
                            <span class="model-icon">${this.host.presentation.getModelIcon(model, pluginName).html}</span>
                            <span class="models-list-title" data-tooltip="${this.host.presentation.sanitizeText(title)}">${this.host.presentation.sanitizeText(title)}</span>
                            ${typeBadge ? `<span class="models-list-title-type">${typeBadge}</span>` : ''}
                            ${buildBadges(model, this.host)}
                        </span>
                        <span class="models-list-subtitle" ${renderLabelAttributes(universalLabel)}>${this.host.presentation.sanitizeText(universalLabel)}</span>
                    </button>
                </td>
                <td class="models-list-cell models-list-type">
                    ${typeBadge}
                </td>
                <td class="models-list-cell models-list-provider">
                    ${providerFact}
                </td>
                <td class="models-list-cell models-list-plugin">
                    <span class="ui-metric-value">${this.host.presentation.sanitizeText(pluginName)}</span>
                </td>
                <td class="models-list-cell models-list-metrics">
                    <div class="ui-collection-list__facts models-list-metrics-facts">${buildModelListMetrics(model, this.host)}</div>
                </td>
                <td class="models-list-cell models-list-status ui-collection-list__state">${statusContent}</td>
                <td class="models-list-cell models-list-actions ui-collection-list__actions">${actionButtons}</td>
            </tr>
        `;
        return this.materializeTableRow(markup);
    }

    override buildContent(model: ModelData, data: CardData): string {
        const pluginName = data.pluginName ?? '';
        const providerName = data.providerName ?? '';
        const originId = data.baseIdentifier || this.host.identity.getModelOriginId(model);
        const cleanId = this.host.identity.extractCleanModelId(originId ?? '');
        const resolvedTitle = this.host.identity.getModelDisplayName(model) || cleanId;
        const badges = buildBadges(model, this.host);
        const metricsResult = buildMetrics(model, providerName, this.host);
        const statusBadgeClass = this.buildClassList([metricsResult.statusBadgeClass]);
        const metricStatusBadgeClass = statusBadgeClass ? `ui-metric-badge--${statusBadgeClass}` : '';
        const statusLabel = this.host.presentation.sanitizeText(metricsResult.statusLabel);
        const universalLabelText = model.type === 'virtual' ? i18n.t('models.virtualModelLabel') : model.universalId || cleanId;
        const universalLabelFull = this.host.presentation.sanitizeText(universalLabelText);
        const universalLabel = universalLabelText.length > 90 ? this.host.presentation.sanitizeText(`${universalLabelText.slice(0, 87)}...`) : universalLabelFull;
        const descriptionText = model.description ? model.description.trim() : '';
        const description = descriptionText ? this.host.presentation.sanitizeText(descriptionText) : '';
        const descriptionTitle = description ? ` data-tooltip="${description}"` : '';
        const descriptionMarkup = description ? `<p class="model-description ui-collection-card__description"${descriptionTitle}>${description}</p>` : '';
        const contentMarkup = descriptionMarkup
            ? `
                <div class="ui-collection-card__content model-card-content">
                    <div class="model-plugin-info ui-collection-card__info">
                        ${descriptionMarkup}
                    </div>
                </div>`
            : '';
        let providerLabel;
        if (model.type === 'virtual') {
            const baseLabel = this.host.presentation.sanitizeText(i18n.t('models.types.virtual'));
            providerLabel = baseLabel ? baseLabel.toLowerCase() : '';
        } else {
            providerLabel = this.host.presentation.sanitizeText(metricsResult.providerLabel ?? '');
        }
        const metricsMarkup = metricsResult.metricsMarkup;
        const iconMarkup = this.host.presentation.getModelIcon(model, pluginName).html;
        const editVirtualLabel = i18n.t('models.actions.editVirtualModel');
        const editParametersLabel = i18n.t('models.actions.editParams');
        const actionMarkup = model.type === 'virtual' ? `<button type="button" class="ui-button ui-button--sm ui-variant-warning" data-action="${MODELS_ACTION_EDIT_VIRTUAL}" ${renderLabelAttributes(editVirtualLabel)}>${editVirtualLabel}</button>` : `<button type="button" class="ui-button ui-button--sm ui-variant-warning" data-action="${MODELS_ACTION_EDIT_PARAMETERS}" ${renderLabelAttributes(editParametersLabel)}>${editParametersLabel}</button>`;
        const modelTypeBadge = buildModelTypeBadge(model, this.host);
        const isDeleting = this.buildStatusClasses(data.statusClass).includes('deleting');
        const deletingOverlay = isDeleting ? `<div class="model-delete-overlay" role="status" aria-live="polite" aria-atomic="true">${this.host.presentation.sanitizeText(i18n.t('models.status.deletingModel'))}</div>` : '';

        return `
                <div class="ui-collection-card__header model-card-header">
                    <div class="ui-collection-card__title-bar model-title-bar">
                        <div class="ui-collection-card__title model-title" data-full-title="${this.host.presentation.sanitizeText(resolvedTitle)}">
                            <span class="ui-collection-card__title-text model-title-text" data-tooltip="${this.host.presentation.sanitizeText(resolvedTitle)}">${this.host.presentation.sanitizeText(resolvedTitle)}</span>
                            ${badges}
                        </div>
                    </div>
                </div>
                <div class="ui-collection-card__subtitle model-universal-id" ${renderLabelAttributes(universalLabelText)}>${universalLabel}</div>
                ${contentMarkup}
                <div class="ui-collection-card__body model-card-body">
                    <div class="ui-collection-card__bottom model-card-bottom">
                        <div class="model-plugin-logo-name ui-collection-card__horizontal">
                            <div class="model-icon">${iconMarkup}</div>
                            <span class="model-plugin-name ui-collection-card__toggle-label">${providerLabel}</span>
                            ${modelTypeBadge}
                        </div>
                        <div class="ui-collection-card__metrics-grid model-metrics-display">${metricsMarkup}</div>
                        <div class="ui-collection-card__status-grid model-metrics-status"><div class="ui-metric-item"><div class="ui-metric-badge ui-metric-badge--status-full ${metricStatusBadgeClass}"><span class="ui-metric-value">${statusLabel}</span></div></div></div>
                    </div>
                </div>
                <div class="model-card-footer">
                    <div class="model-actions">
                        ${actionMarkup}
                    </div>
                </div>
                ${deletingOverlay}
            `;
    }

    override buildActionButtons(model?: ModelData | null): ButtonConfig[] {
        if (!model) {
            throw new TypeError('ModelCardRenderer.buildActionButtons requires model data');
        }
        const buttons: ButtonConfig[] = [];
        const deleteButton = this.buildDeleteAction(model);
        if (deleteButton) {
            buttons.push(deleteButton);
        }
        const stopButton = this.buildStopAction(model);
        if (stopButton) {
            buttons.push(stopButton);
        }
        const editButton = this.buildEditAction(model);
        if (editButton) {
            buttons.push(editButton);
        }
        return buttons;
    }

    buildDeleteAction(model: ModelData): ButtonConfig | null {
        if (!this.host.status.canDeleteModel(model)) {
            return null;
        }
        const label = this.host.presentation.sanitizeText(i18n.t('models.actions.deleteModel'));
        return this.createRoundButton({
            className: this.buildClassList(['ui-round-button', 'ui-round-button--delete']),
            action: MODELS_ACTION_DELETE,
            iconName: 'close',
            iconOptions: { strokeWidth: 1.5 },
            label
        });
    }

    buildStopAction(model: ModelData): ButtonConfig | null {
        if (!this.isModelStoppable(model)) {
            return null;
        }
        const label = this.host.presentation.sanitizeText(i18n.t('models.actions.stopModel'));
        return this.createRoundButton({
            className: this.buildClassList(['ui-round-button', 'ui-round-button--stop']),
            action: MODELS_ACTION_STOP_MODEL,
            iconName: 'stop',
            iconOptions: { strokeWidth: 1.5 },
            label
        });
    }

    buildEditAction(model: ModelData): ButtonConfig | null {
        if (model?.type === 'virtual') {
            return this.createRoundButton({
                className: 'ui-round-button ui-round-button--settings',
                action: MODELS_ACTION_EDIT_VIRTUAL,
                iconName: 'settings',
                iconOptions: { strokeWidth: 1.5 },
                label: this.host.presentation.sanitizeText(i18n.t('models.actions.editVirtualModel'))
            });
        }
        const label = this.host.presentation.sanitizeText(i18n.t('models.actions.editModel'));
        return this.createRoundButton({
            className: 'ui-round-button ui-round-button--edit',
            action: MODELS_ACTION_EDIT_MODEL,
            iconName: 'model-config',
            iconOptions: { strokeWidth: 1 },
            label
        });
    }

    buildListActionButtons(model: ModelData): string {
        const buttons: string[] = [];
        const appendButton = (action: string, iconName: 'close' | 'model-config' | 'settings' | 'stop', className: string, label: string, strokeWidth: number): void => {
            buttons.push(
                this.cards.button({
                    className,
                    dataset: { action },
                    aria: { label },
                    attributes: { type: 'button' },
                    icon: { name: iconName, options: { strokeWidth } }
                })
            );
        };
        if (model.type !== 'virtual') {
            appendButton(MODELS_ACTION_EDIT_MODEL, 'model-config', 'ui-round-button ui-round-button--inline ui-round-button--edit', i18n.t('models.actions.editModel'), 1);
            appendButton(MODELS_ACTION_EDIT_PARAMETERS, 'settings', 'ui-round-button ui-round-button--inline ui-round-button--settings ui-round-button--modal-close', i18n.t('models.actions.editParams'), 1.5);
        } else {
            appendButton(MODELS_ACTION_EDIT_VIRTUAL, 'settings', 'ui-round-button ui-round-button--inline ui-round-button--settings ui-round-button--modal-close', i18n.t('models.actions.editVirtualModel'), 1.5);
        }
        if (this.isModelStoppable(model)) {
            appendButton(MODELS_ACTION_STOP_MODEL, 'stop', 'ui-round-button ui-round-button--inline ui-round-button--stop', i18n.t('models.actions.stopModel'), 1.5);
        }
        if (this.host.status.canDeleteModel(model)) {
            appendButton(MODELS_ACTION_DELETE, 'close', 'ui-round-button ui-round-button--inline ui-round-button--delete', i18n.t('models.actions.deleteModel'), 1.5);
        }
        return buttons.join('');
    }

    buildListStatusContent(model: ModelData, statusLabel: string, statusBadgeClass: string): string {
        const toggleMarkup = buildModelListEnabledToggle(model, this.host);
        const statusMarkup = buildModelListStatus(statusLabel, statusBadgeClass, this.host);
        return `${toggleMarkup}${statusMarkup}`;
    }

    private isModelStoppable(model: ModelData): boolean {
        const status = this.host.status.getModelStatus(model);
        return Boolean(status && model.type !== 'virtual' && !this.host.status.isModelFromPersistentPlugin(model) && this.activeStatuses.includes(status));
    }
}

export { ModelCardRenderer };
