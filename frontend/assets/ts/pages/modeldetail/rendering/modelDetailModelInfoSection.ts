/* SoAI - Model detail information section rendering [frontend/assets/ts/pages/modeldetail/rendering/modelDetailModelInfoSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatPercentFromFraction } from '@core/primitives/percent.ts';
import { capitalize } from '@core/primitives/text.ts';
import { isArray, isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { formatModelDetailDateTime } from '@pages/modeldetail/formatting/modelDetailFormatting.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type InfoFormatter = (value: JsonValue | null | undefined) => string | null;
type InfoField = [string, JsonValue | null | undefined, InfoFormatter?];

interface ModelDetailModelInfoHost extends PageDomOwnerHost {
    model: ModelRecord;
    getModelDisplayName(): string;
    isVirtualModel(): boolean;
    getPluginStatus(): string | null;
    describePluginStatus(value: string): string;
    setInfo(id: string, value: JsonValue | null | undefined, formatter?: InfoFormatter): void;
    populateDetailCards(): void;
    sanitizeAttribute(value: string): string;
    sanitizeText(value: JsonValue | null | undefined): string;
    getStopPluginButton(): HTMLElement | null;
    getManageAliasButton(): HTMLElement | null;
    updateBackendDocButtonVisibility(): void;
    updateHeaderInfo(): void;
}

const STOP_PLUGIN_ALLOWED_STATES = new Set(['IDLE', 'READY', 'READY_PENDING_DISPATCH', 'READY_DIRTY', 'PROCESSING', 'LOADING', 'STARTING']);

const renderVirtualConstituentList = (host: ModelDetailModelInfoHost, model: ModelRecord): string => {
    if (!isArray(model.models)) {
        throw new TypeError('virtual model constituents must be an array');
    }
    const rows = model.models.map((entry: JsonValue | null) => {
        if (!isObject(entry)) {
            throw new TypeError('Virtual model constituent entry must be an object');
        }
        const nameCandidate = entry['name'] ?? entry['id'] ?? entry['universalId'];
        const universalIdCandidate = entry['universalId'] ?? entry['id'] ?? nameCandidate;
        const name = isString(nameCandidate) || isNumber(nameCandidate) ? String(nameCandidate) : null;
        const universalId = isString(universalIdCandidate) || isNumber(universalIdCandidate) ? String(universalIdCandidate) : null;
        if (!name || !universalId) {
            throw new Error('Virtual model constituent entry missing identifiers');
        }
        const parametersCandidate = entry['parameters'];
        const hasParameters = isObject(parametersCandidate) && Object.keys(parametersCandidate).length > 0;
        const title = host.sanitizeAttribute(name);
        const safeName = host.sanitizeText(name);
        const safeUniversalId = host.sanitizeText(universalId);
        return `<div class="modeldetail-constituent-item glass-surface-medium"><div class="modeldetail-constituent-name" data-tooltip="${title}">${safeName}</div><div class="modeldetail-constituent-uid">${safeUniversalId}</div>${hasParameters ? `<span class="modeldetail-constituent-badge">${i18n.t('modelDetail.cards.constituents.hasParameters')}</span>` : ''}</div>`;
    });
    return rows.join('') || `<div class="modeldetail-empty-state">${i18n.t('modelDetail.cards.constituents.noModels')}</div>`;
};

const populateModelDetailModelInfo = (host: ModelDetailModelInfoHost): void => {
    const model = host.model;
    host.updateHeaderInfo();
    const isVirtual = host.isVirtualModel();
    const enabledValue = isBoolean(model.isEnabled) ? model.isEnabled : true;
    const isDisabled = !isVirtual && !enabledValue;
    const typeValue = model.type;
    const normalizedType = isString(typeValue) ? typeValue.trim() : '';
    const typeLabel = (() => {
        if (isVirtual) {
            return `${i18n.t('modelDetail.cards.identity.virtual')} (${model.strategy || i18n.t('models.types.unknown')})`;
        }
        if (normalizedType === 'local') {
            return i18n.t('models.types.local');
        }
        if (normalizedType === 'virtual') {
            return i18n.t('models.types.virtual');
        }
        if (!normalizedType) {
            return i18n.t('models.types.unknown');
        }
        return capitalize(normalizedType);
    })();
    const fields: InfoField[] = [
        ['modeldetail-display-name', host.getModelDisplayName()],
        ['modeldetail-source-model-id', model.sourceModelId],
        ['modeldetail-universal-id', model.universalId],
        ['modeldetail-provider', model.plugin || model.provider],
        ['modeldetail-type', typeLabel],
        ['modeldetail-repository', model.modelRepository],
        ['modeldetail-path', model.path],
        ['modeldetail-size', model.sizeBytes, (value: JsonValue | null | undefined) => (isNumber(value) ? formatBytes(value) : null)],
        ['modeldetail-family', model.family],
        ['modeldetail-quantization', model.quantization],
        ['modeldetail-license', model.license],
        ['modeldetail-created', model.createdAtMs, (value: JsonValue | null | undefined) => (isNumber(value) ? formatModelDetailDateTime(value) : null)],
        ['modeldetail-description', model.description],
        ['modeldetail-plugin-status', host.getPluginStatus(), (value: JsonValue | null | undefined) => (isString(value) ? host.describePluginStatus(value) : null)],
        ['modeldetail-model-status', isBoolean(model.isLoaded) ? (model.isLoaded ? i18n.t('modelDetail.status.loaded') : i18n.t('modelDetail.status.unloaded')) : null],
        ['modeldetail-available', isBoolean(model.isAvailable) ? (model.isAvailable ? i18n.t('modelDetail.status.yes') : i18n.t('modelDetail.status.no')) : null],
        ['modeldetail-orphaned', model.isOrphaned ? i18n.t('modelDetail.status.yes') : null],
        ['modeldetail-total-requests', null],
        ['modeldetail-tokens-generated', null],
        ['modeldetail-modality-usage', null],
        ['modeldetail-avg-tokens', model.averageTokens, (value: JsonValue | null | undefined) => (isNumber(value) ? i18n.formatNumber(Math.round(value)) : null)],
        ['modeldetail-success-rate', model.successRate, (value: JsonValue | null | undefined) => (isNumber(value) ? formatPercentFromFraction(value) : null)],
        ['modeldetail-failed-requests', null],
        ['modeldetail-avg-latency', null],
        ['modeldetail-wait-time', null],
        ['modeldetail-last-used', model.lastUsedAtMs, (value: JsonValue | null | undefined) => (isNumber(value) ? formatModelDetailDateTime(value) : null)]
    ];
    fields.forEach((field) => host.setInfo(field[0], field[1], field[2]));

    const availableValue = model.isAvailable;
    const highlightAvailableNo = isDisabled && isBoolean(availableValue) && !availableValue;
    const availableElement = host.pageDom.optionalHTMLElement('modeldetail-available');
    if (availableElement) {
        host.pageDom.toggleClass(availableElement, 'u-text-status-orange', highlightAvailableNo);
    }

    const constituentsCard = host.pageDom.optionalHTMLElement('modeldetail-constituents-card');
    if (isVirtual) {
        if (constituentsCard) host.pageDom.removeClass(constituentsCard, 'u-hidden');
        const list = host.pageDom.optionalHTMLElement('modeldetail-constituent-list');
        if (list) {
            const constituentMarkup = toTrustedUiHtml(renderVirtualConstituentList(host, model));
            host.pageDom.updateHtml(list, constituentMarkup);
        }
    } else if (constituentsCard) {
        host.pageDom.addClass(constituentsCard, 'u-hidden');
    }

    const stopButton = host.getStopPluginButton();
    const pluginStatus = host.getPluginStatus();
    if (stopButton) {
        const shouldHide = isVirtual || pluginStatus === 'PERSISTENT_READY' || !STOP_PLUGIN_ALLOWED_STATES.has(pluginStatus ?? '');
        host.pageDom.toggleClass(stopButton, 'u-hidden', shouldHide);
    }
    const manageAliasButton = host.getManageAliasButton();
    if (manageAliasButton) {
        host.pageDom.toggleClass(manageAliasButton, 'u-hidden', isVirtual);
    }
    host.updateBackendDocButtonVisibility();
    host.populateDetailCards();
};

export { populateModelDetailModelInfo };
export type { ModelDetailModelInfoHost };
