/* SoAI - Models feature OpenAI capability rendering [frontend/assets/ts/features/models/capabilities/openaiCapabilityRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isOpenAICapabilityEnabled } from '@core/openai/capabilityChecks.ts';
import { escapeAttribute, escapeHtml } from '@core/security/textSanitizer.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, isOpenAICapabilityDisabled, isSafeOpenAICapabilityToken, normalizeOverrideToken, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideState } from '@features/models/capabilities/openaiCapabilityState.ts';
import { EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY } from '@features/models/modals/constants.ts';

interface OpenAICapabilityRenderingHost {
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
}

interface OpenAICapabilityRenderInput {
    model: ModelRecord;
    plugin: PluginRecord | null;
    manifest: JsonObject | null;
    state: OpenAICapabilityOverrideState;
    host: OpenAICapabilityRenderingHost;
}

const extractManifestTokens = (manifest: JsonObject, category: OpenAICapabilityOverrideCategory): string[] => {
    const raw = manifest[category];
    if (!isJsonArray(raw)) {
        return [];
    }
    return raw.map((entry): string => (isString(entry) ? normalizeOverrideToken(entry) : '')).filter((token: string): boolean => Boolean(token) && isSafeOpenAICapabilityToken(token));
};

const extractPluginModalities = (plugin: PluginRecord | null): string[] => {
    if (!plugin || !Array.isArray(plugin.modalities)) {
        return [];
    }
    const normalized: string[] = [];
    for (const entry of plugin['modalities']) {
        if (!isString(entry)) {
            continue;
        }
        const token = normalizeOverrideToken(entry);
        if (token && isSafeOpenAICapabilityToken(token)) {
            normalized.push(token);
        }
    }
    return Array.from(new Set(normalized));
};

const extractModelModalities = (model: ModelRecord): string[] => {
    if (!Array.isArray(model.modalities)) {
        return ['text'];
    }
    const normalized = model.modalities.map((entry): string => (isString(entry) ? normalizeOverrideToken(entry) : '')).filter((token: string): boolean => Boolean(token) && isSafeOpenAICapabilityToken(token));
    return normalized.includes('text') ? normalized : ['text', ...normalized];
};

const getPluginOpenAIRecord = (plugin: PluginRecord | null): JsonObject | null => {
    const pluginOpenAI = plugin?.capabilities?.openai;
    return isJsonObject(pluginOpenAI) ? pluginOpenAI : null;
};

const resolveSectionLabel = (category: OpenAICapabilityOverrideCategory): string => {
    switch (category) {
        case 'endpoints':
            return i18n.t('modelDetail.cards.capabilities.sections.endpoints');
        case 'responses_features':
            return i18n.t('modelDetail.cards.capabilities.sections.responsesFeatures');
        case 'image_features':
            return i18n.t('modelDetail.cards.capabilities.sections.imageFeatures');
        case 'chat_features':
            return i18n.t('modelDetail.cards.capabilities.sections.chatFeatures');
        case 'modalities':
            return i18n.t('modelDetail.cards.capabilities.sections.modalities');
    }
};

const resolveVisibleModalities = (input: OpenAICapabilityRenderInput, manifest: JsonObject): string[] => {
    const manifestModalities = extractManifestTokens(manifest, 'modalities');
    const pluginModalities = extractPluginModalities(input.plugin);
    const modelModalities = extractModelModalities(input.model);
    const baseModalities = pluginModalities.length ? pluginModalities : modelModalities;
    return manifestModalities.length ? manifestModalities.filter((token) => token === 'text' || baseModalities.includes(token) || isOpenAICapabilityDisabled(input.state.originalDisabled, 'modalities', token)) : baseModalities;
};

const resolveEffectiveModalities = (input: OpenAICapabilityRenderInput, manifest: JsonObject): ReadonlySet<string> => {
    const visibleModalities = resolveVisibleModalities(input, manifest);
    const effective = new Set<string>();
    for (const token of visibleModalities) {
        if (token === 'text' || !isOpenAICapabilityDisabled(input.state.currentDisabled, 'modalities', token)) {
            effective.add(token);
        }
    }
    effective.add('text');
    return effective;
};

const isCapabilityChecked = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string): boolean => {
    if (isOpenAICapabilityDisabled(input.state.currentDisabled, category, token)) {
        return false;
    }
    if (isOpenAICapabilityDisabled(input.state.originalDisabled, category, token)) {
        return true;
    }
    if (category === 'modalities') {
        return extractModelModalities(input.model).includes(token);
    }
    const modelOpenAI = input.model.openaiCapabilities;
    return isOpenAICapabilityEnabled(modelOpenAI, category, token);
};

const buildLockedReason = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string, effectiveModalities: ReadonlySet<string>): string | null => {
    if (category === 'modalities') {
        return token === 'text' ? i18n.t('modelDetail.cards.capabilities.lockedReasons.text') : null;
    }
    if (category === 'responses_features' && !isCapabilityChecked(input, 'endpoints', 'responses')) {
        return i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresResponses');
    }
    if (category === 'image_features' && !isCapabilityChecked(input, 'endpoints', 'images')) {
        return i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresImages');
    }
    if (category === 'chat_features' && token === 'vision' && !effectiveModalities.has('vision')) {
        return i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresVision');
    }
    if (category === 'chat_features' && token === 'input_audio' && !effectiveModalities.has('audio')) {
        return i18n.t('modelDetail.cards.capabilities.lockedReasons.requiresAudio');
    }
    return null;
};

const renderCapabilityRow = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string, lockedReason: string | null): string => {
    if (!isSafeOpenAICapabilityToken(token) || !isSafeOpenAICapabilityToken(category)) {
        return '';
    }
    const host = input.host;
    const checked = lockedReason ? category === 'modalities' && token === 'text' : isCapabilityChecked(input, category, token);
    const checkedAttr = checked ? ' checked' : '';
    const disabledAttr = lockedReason ? ' disabled' : '';
    const lockedData = lockedReason ? ' data-toggle-locked="true" aria-disabled="true"' : ' aria-disabled="false"';
    const disabledOriginally = isOpenAICapabilityDisabled(input.state.originalDisabled, category, token);
    const disabledCurrently = isOpenAICapabilityDisabled(input.state.currentDisabled, category, token);
    const dirty = disabledOriginally !== disabledCurrently;
    const overridden = disabledCurrently;
    const reasonHtml = lockedReason ? `<div class="openai-capability-reason">${escapeHtml(lockedReason)}</div>` : '';
    const label = host.resolveOpenAICapabilityLabel(category, token);
    return `<div class="openai-capability-row setting-change-surface${dirty ? ' modified' : ''}${overridden ? ' is-overridden' : ''}${lockedReason ? ' is-locked' : ''}">
        <div class="openai-capability-meta">
            <div class="openai-capability-label">
                <span class="openai-capability-name">${escapeHtml(label)}</span>
            </div>
            ${reasonHtml}
        </div>
        <label class="toggle-switch openai-capability-toggle" data-action="${escapeAttribute(EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY)}" data-category="${escapeAttribute(category)}" data-token="${escapeAttribute(token)}"${lockedData}>
            <input type="checkbox" aria-label="${escapeAttribute(label)}"${checkedAttr}${disabledAttr}>
            <span class="slider"></span>
        </label>
    </div>`;
};

const renderOpenAICapabilityOverrides = (input: OpenAICapabilityRenderInput): string => {
    if (!input.manifest) {
        return `<div class="openai-capabilities-message">${escapeHtml(i18n.t('modelDetail.cards.capabilities.manifestLoading'))}</div>`;
    }
    const pluginOpenAIRecord = getPluginOpenAIRecord(input.plugin);
    const pluginModalities = extractPluginModalities(input.plugin);
    if (!pluginOpenAIRecord && pluginModalities.length === 0) {
        return `<div class="openai-capabilities-message">${escapeHtml(i18n.t('modelDetail.cards.capabilities.pluginCapabilitiesUnavailable'))}</div>`;
    }
    const effectiveModalities = resolveEffectiveModalities(input, input.manifest);
    const sections: string[] = [];
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const rows: string[] = [];
        const tokens = category === 'modalities' ? resolveVisibleModalities(input, input.manifest) : extractManifestTokens(input.manifest, category);
        for (const token of tokens) {
            if (category !== 'modalities') {
                if (!pluginOpenAIRecord || !isOpenAICapabilityEnabled(pluginOpenAIRecord, category, token)) {
                    continue;
                }
            }
            rows.push(renderCapabilityRow(input, category, token, buildLockedReason(input, category, token, effectiveModalities)));
        }
        const renderedRows = rows.filter(Boolean).join('');
        if (renderedRows) {
            sections.push(`<div class="openai-capabilities-category" data-category="${escapeAttribute(category)}"><div class="openai-capabilities-category-title">${escapeHtml(resolveSectionLabel(category))}</div></div>`);
            sections.push(`<div class="openai-capabilities-category-rows">${renderedRows}</div>`);
        }
    }
    return sections.length ? `<div class="openai-capabilities-overrides">${sections.join('')}</div>` : `<div class="openai-capabilities-message">${escapeHtml(i18n.t('modelDetail.cards.capabilities.none'))}</div>`;
};

export { renderOpenAICapabilityOverrides };
