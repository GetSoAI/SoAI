/* SoAI - Plugins page card renderer service [frontend/assets/ts/pages/plugins/rendering/cardrenderer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { BaseCardRenderer, type RoundButtonConfig } from '@core/ui/BaseCardRenderer.ts';
import type { ButtonConfig, DatasetProps } from '@core/uiprimitives/public.ts';
import { PLUGINS_ACTION_CLONE_PLUGIN, PLUGINS_ACTION_DELETE_PLUGIN, PLUGINS_ACTION_EDIT_CONFIG, PLUGINS_ACTION_METRIC_BADGE, PLUGINS_ACTION_OPEN_PLUGIN, PLUGINS_ACTION_STOP_PLUGIN } from '@features/plugins/public.ts';
import { prepareCardData, resolveActionState } from '@pages/plugins/rendering/cardrenderer/mappers.ts';
import { buildPluginEnabledToggle, resolveToggleLabelText } from '@pages/plugins/rendering/cardrenderer/rendering.ts';
import { buildPluginListActionConfigs } from '@pages/plugins/rendering/cardrenderer/listRowActionsWidget.ts';
import { resolveToggleChecked } from '@pages/plugins/rendering/cardrenderer/pluginCardToggleStateWidget.ts';
import type { ActionContext, ActionState, PluginCardData, PluginCardHost, PluginCardRendererConstants, PluginCardRendererOptions, PluginRecord } from '@pages/plugins/rendering/cardrenderer/types.ts';
import { renderCardContent } from '@pages/plugins/rendering/cardrenderer/view.ts';

interface PluginListFact {
    metricKey: string;
    label: string;
    value: string | number;
    clickable: boolean;
}

class PluginCardRenderer extends BaseCardRenderer<PluginRecord | null | undefined, PluginCardData> {
    protected override host: PluginCardHost;
    protected constants: PluginCardRendererConstants;

    constructor(options: PluginCardRendererOptions) {
        super({ host: options.host });
        const { host, constants } = options;
        this.host = host;

        if (!constants.classNames.disabled) {
            throw new Error('PluginCardRenderer requires disabled class name');
        }
        if (!constants.statuses.backendNotInstalled || !constants.statuses.backendInstalling || !constants.statuses.incompatible || !constants.statuses.quarantined) {
            throw new Error('PluginCardRenderer requires status descriptors');
        }

        this.constants = {
            classNames: { disabled: constants.classNames.disabled },
            statuses: {
                backendNotInstalled: constants.statuses.backendNotInstalled,
                backendInstalling: constants.statuses.backendInstalling,
                incompatible: constants.statuses.incompatible,
                quarantined: constants.statuses.quarantined
            }
        };
    }

    override render(plugin: PluginRecord | null | undefined): HTMLElement | null {
        if (!plugin) return null;
        const data = this.prepareCardData(plugin);
        return data.cardId ? this.buildCardElement(plugin, data) : null;
    }

    renderListRow(plugin: PluginRecord | null | undefined): HTMLElement | null {
        if (!plugin) return null;
        const data = this.prepareCardData(plugin);
        if (!data.cardId) return null;
        const permanentlyDisabled = this.host.compatibility.isPluginPermanentlyDisabled(plugin);
        const hardwareIncompatible = data.hardwareIncompatible === true;
        const circuitBreakerActive = data.circuitBreakerActive === true;
        const quarantined = circuitBreakerActive || data.status === this.constants.statuses.quarantined;
        const quarantineLocked = quarantined && !circuitBreakerActive;
        const overrideRequired = data.overrideRequired;
        const toggleLocked = permanentlyDisabled || (!hardwareIncompatible && data.overrideRequired) || quarantineLocked;
        const lockState = toggleLocked || hardwareIncompatible || circuitBreakerActive;
        const actionState = this.resolveActionState(plugin, lockState);
        const compatibility = this.host.compatibility.getPluginCompatibility(plugin);
        const overrideActive = Boolean(compatibility?.isOverridden);
        const pendingToggleTarget = this.host.actions.getPendingToggleTarget(plugin);
        const forceToggleUnchecked = toggleLocked || hardwareIncompatible || circuitBreakerActive;
        const compatibilityIncompatible = permanentlyDisabled || hardwareIncompatible;
        const toggleChecked = resolveToggleChecked(plugin.isEnabled, plugin.state, forceToggleUnchecked, pendingToggleTarget);
        const toggleLabel = resolveToggleLabelText(permanentlyDisabled, quarantined, overrideRequired, overrideActive, toggleChecked);
        const safeName = this.host.presentation.sanitizeText(this.host.presentation.formatPluginName(plugin.name) || i18n.t('common.unknown'));
        const listTitle = compatibilityIncompatible ? `${safeName} (${this.host.presentation.sanitizeText(i18n.t('plugins.status.incompatible'))})` : safeName;
        const description = this.host.presentation.sanitizeText(plugin.descriptionSoaiplugin?.trim() ?? '');
        const typeLabel = plugin.isBuiltin ? i18n.t('plugins.badges.builtin') : i18n.t('plugins.badges.thirdparty');
        const statusClass = this.buildClassList([data.statusBadgeClass]);
        const pluginLogo = this.host.presentation.getPluginLogo(plugin);
        const pluginLogoFallback = this.host.presentation.getPluginLogoFallback(plugin);
        const facts: readonly PluginListFact[] = [
            {
                metricKey: 'version',
                label: i18n.t('plugins.badges.version'),
                value: plugin.versionSoaiplugin || i18n.t('common.notAvailableShort'),
                clickable: true
            },
            { metricKey: 'models', label: i18n.t('plugins.badges.models'), value: plugin.stats?.modelCount || 0, clickable: true },
            { metricKey: 'type', label: i18n.t('plugins.badges.type'), value: typeLabel, clickable: false }
        ];
        const markup = `
            <tr class="${this.builder.combineClasses('plugins-list-row', data.statusClass, compatibilityIncompatible ? 'plugins-list-row--incompatible' : '', !toggleChecked ? this.constants.classNames.disabled : '', this.host.actions.isNewItem(plugin) ? 'session-recent-row' : '')}" data-render-mode="list" data-action="${PLUGINS_ACTION_OPEN_PLUGIN}" data-plugin="${this.host.presentation.sanitizeText(data.cardId)}" data-status="${this.host.presentation.sanitizeText(data.status)}" data-circuit-breaker="${circuitBreakerActive ? 'active' : 'inactive'}">
                <td class="plugins-list-cell plugins-list-cell-main">
                    <button type="button" class="plugins-list-open" data-action="${PLUGINS_ACTION_OPEN_PLUGIN}" ${renderLabelAttributes(listTitle)}>
                        <span class="plugins-list-title-row">
                            ${pluginLogo ? `<img src="${this.host.presentation.sanitizeText(pluginLogo)}" data-plugin-logo-fallback="${this.host.presentation.sanitizeText(pluginLogoFallback)}" alt="" class="plugin-logo-small" />` : ''}
                            <span class="plugins-list-title" data-tooltip="${listTitle}">${listTitle}</span>
                        </span>
                        <span class="plugins-list-description">${description}</span>
                    </button>
                </td>
                <td class="plugins-list-cell plugins-list-metrics">
                    <div class="ui-collection-list__facts">${this.renderListFacts(facts)}</div>
                </td>
                <td class="plugins-list-cell plugins-list-status ui-collection-list__state">
                    ${buildPluginEnabledToggle({
                        permanentlyDisabled,
                        circuitBreakerActive,
                        locked: toggleLocked,
                        checked: toggleChecked,
                        available: hardwareIncompatible ? true : plugin.isAvailable !== false,
                        pendingToggleTarget,
                        disabledClassName: this.constants.classNames.disabled,
                        label: toggleLabel,
                        showLabel: true
                    })}
                    <span class="ui-collection-list__status ${statusClass}"><span class="status-led status-led-sm status-led-no-margin" aria-hidden="true"></span><span>${this.host.presentation.sanitizeText(permanentlyDisabled ? i18n.t('plugins.status.incompatible') : quarantined ? i18n.t('plugins.status.quarantined') : data.statusLabel)}</span></span>
                </td>
                <td class="plugins-list-cell plugins-list-actions ui-collection-list__actions">${this.buildListActionButtons(plugin, actionState)}</td>
            </tr>
        `;
        return this.materializeTableRow(markup);
    }

    override prepareCardData(plugin: PluginRecord): PluginCardData {
        return prepareCardData(this.host, plugin);
    }

    buildCardElement(plugin: PluginRecord, data: PluginCardData): HTMLElement | null {
        const { host, constants } = this;
        const { hardwareIncompatible, statusClass, circuitBreakerActive, overrideRequired, cardId } = data;

        const permanentlyDisabled = host.compatibility.isPluginPermanentlyDisabled(plugin);
        const hardwareIncompatibleBool = hardwareIncompatible === true;
        const circuitBreakerIncompatible = circuitBreakerActive === true;
        const quarantined = circuitBreakerIncompatible || data.status === constants.statuses.quarantined;
        const quarantineLocked = quarantined && !circuitBreakerIncompatible;
        const lockState = permanentlyDisabled || (overrideRequired && !hardwareIncompatibleBool) || quarantineLocked;
        const actionsLocked = lockState || hardwareIncompatibleBool || circuitBreakerIncompatible;
        const actionState = this.resolveActionState(plugin, actionsLocked);
        const pendingToggleTarget = host.actions.getPendingToggleTarget(plugin);
        const visuallyEnabled = resolveToggleChecked(plugin.isEnabled, plugin.state, actionsLocked, pendingToggleTarget);

        const cardDataset: DatasetProps = {
            plugin: cardId ?? undefined,
            status: data.status,
            'circuit-breaker': circuitBreakerActive ? 'active' : 'inactive'
        };

        if (lockState) {
            cardDataset['plugin-lock'] = quarantineLocked ? 'quarantine' : 'compatibility';
        } else if (circuitBreakerActive) {
            cardDataset['plugin-lock'] = 'circuit-breaker';
        }

        const incompatibleClasses = this.builder.combineClasses((lockState || hardwareIncompatibleBool) && !quarantineLocked ? 'plugin-card--incompatible' : '', hardwareIncompatibleBool ? 'plugin-card--hardware-incompatible' : '', circuitBreakerIncompatible ? 'plugin-card--circuit-breaker' : '', quarantineLocked ? 'plugin-card--quarantined' : '');
        const recentClass = host.actions.isNewItem(plugin) ? 'session-recent-card' : '';

        const element = this.materialize(
            toTrustedUiHtml(
                this.cards.card({
                    className: this.builder.combineClasses('plugin-card', statusClass, recentClass, !visuallyEnabled ? constants.classNames.disabled : '', incompatibleClasses),
                    dataset: cardDataset,
                    actions: this.buildPluginActionButtons({
                        plugin,
                        actionState
                    }),
                    children: this.renderCardContent(plugin, data),
                    statusLine: {
                        className: this.builder.combineClasses('plugin-status-line', statusClass)
                    }
                })
            )
        );
        return element instanceof HTMLElement ? element : null;
    }

    buildPluginActionButtons(context: ActionContext): ButtonConfig[] {
        const { plugin, actionState } = context;
        const buttons: RoundButtonConfig[] = [
            {
                action: PLUGINS_ACTION_DELETE_PLUGIN,
                className: 'ui-round-button ui-round-button--delete',
                iconName: 'close',
                iconOptions: { strokeWidth: 1.5 },
                label: i18n.t('plugins.actions.deletePlugin')
            }
        ];

        if (this.host.actions.isPluginStoppable(plugin)) {
            buttons.push({
                action: PLUGINS_ACTION_STOP_PLUGIN,
                className: 'ui-round-button ui-round-button--stop',
                iconName: 'stop',
                iconOptions: { strokeWidth: 1.5 },
                label: i18n.t('plugins.actions.stopPlugin')
            });
        }

        if (actionState.hasConfigAction) {
            buttons.push({
                action: PLUGINS_ACTION_EDIT_CONFIG,
                className: 'ui-round-button ui-round-button--edit ui-round-button--edit-config',
                iconName: 'model-config',
                iconOptions: { strokeWidth: 1 },
                label: i18n.t('plugins.actions.editConfig')
            });
        }

        if (actionState.hasCloneAction) {
            buttons.push({
                action: PLUGINS_ACTION_CLONE_PLUGIN,
                className: 'ui-round-button ui-round-button--clone',
                iconName: 'copy',
                iconOptions: { strokeWidth: 1 },
                label: i18n.t('plugins.actions.clonePlugin')
            });
        }

        return buttons.map((button) => this.createRoundButton(button));
    }

    private resolveActionState(plugin: PluginRecord, lockState: boolean): ActionState {
        return resolveActionState(this.host, plugin, lockState);
    }

    renderCardContent(plugin: PluginRecord, data: PluginCardData): string {
        return renderCardContent({
            plugin,
            data,
            host: this.host,
            constants: this.constants
        });
    }

    buildListActionButtons(plugin: PluginRecord, actionState: ActionState): string {
        const buttons = buildPluginListActionConfigs(plugin, actionState, this.host);
        return buttons
            .map((button) => {
                const className = `${button.className} ui-round-button--inline`;
                return this.cards.button(this.createRoundButton({ ...button, className }));
            })
            .join('');
    }

    private renderListFacts(facts: readonly PluginListFact[]): string {
        return facts.map((fact) => this.renderListFact(fact)).join('');
    }

    private renderListFact(fact: PluginListFact): string {
        const tagName = fact.clickable ? 'button' : 'span';
        const typeAttribute = fact.clickable ? ' type="button"' : '';
        const actionAttribute = fact.clickable ? ` data-action="${PLUGINS_ACTION_METRIC_BADGE}"` : '';
        const actionClass = fact.clickable ? ' ui-collection-list__fact--action' : '';
        const metricKey = this.cards.escapeAttribute(fact.metricKey);
        const label = this.cards.escapeHtml(fact.label);
        const value = this.cards.escapeHtml(String(fact.value));
        return `<${tagName}${typeAttribute} class="ui-collection-list__fact${actionClass}"${actionAttribute} data-metric-key="${metricKey}"><span class="ui-metric-label">${label}</span><span class="ui-metric-value">${value}</span></${tagName}>`;
    }
}

export { PluginCardRenderer };
