/* SoAI - Models feature OpenAI capability rendering [frontend/assets/ts/features/models/capabilities/openaiCapabilityRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveOpenAICapabilityRequirement, type OpenAICapabilityRequirement } from '@features/models/capabilities/openaiCapabilityDependencies.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import { i18n } from '@core/i18n/index.ts';
import { hasOpenAIModality, isOpenAICapabilityEnabled } from '@core/openai/capabilityChecks.ts';
import { escapeAttribute, escapeHtml } from '@core/security/textSanitizer.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, isSafeOpenAICapabilityToken, normalizeOverrideToken, resolveOpenAICapabilityOverrideMode, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideMode, type OpenAICapabilityOverrideState } from '@features/models/capabilities/openaiCapabilityState.ts';
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

interface OpenAICapabilityRowState {
    mode: OpenAICapabilityOverrideMode;
    autoSupported: boolean;
    lockedReason: string | null;
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
    return manifestModalities.length ? manifestModalities.filter((token) => token === 'text' || baseModalities.includes(token) || resolveOpenAICapabilityOverrideMode(input.state.original, 'modalities', token) !== 'auto') : baseModalities;
};

const isCapabilityAdvertisedByModel = (model: ModelRecord, category: OpenAICapabilityOverrideCategory, token: string): boolean => {
    if (category === 'modalities') {
        return hasOpenAIModality(model.openaiBaseProfile?.['modalities'], token);
    }
    const modelOpenAI = model.openaiBaseProfile?.['openai_capabilities'];
    return isOpenAICapabilityEnabled(isJsonObject(modelOpenAI) ? modelOpenAI : null, category, token);
};

const isCapabilitySupportedByModel = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string): boolean => {
    const linkedModality = token === 'vision' ? 'vision' : token === 'input_audio' ? 'audio' : null;
    const linkedFeature = token === 'vision' ? 'vision' : token === 'audio' ? 'input_audio' : null;
    if ((category === 'chat_features' && linkedModality !== null && resolveOpenAICapabilityOverrideMode(input.state.current, 'modalities', linkedModality) === 'enabled') || (category === 'modalities' && linkedFeature !== null && resolveOpenAICapabilityOverrideMode(input.state.current, 'chat_features', linkedFeature) === 'enabled')) {
        return true;
    }
    return isCapabilityAdvertisedByModel(input.model, category, token);
};

const isCapabilityEffective = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string): boolean => {
    if (category === 'modalities' && token === 'text') {
        return true;
    }
    if (category === 'modalities') {
        const pluginModalities = extractPluginModalities(input.plugin);
        if (pluginModalities.length && !pluginModalities.includes(token)) return false;
    } else if (!isOpenAICapabilityEnabled(getPluginOpenAIRecord(input.plugin), category, token)) {
        return false;
    }
    const mode = resolveOpenAICapabilityOverrideMode(input.state.current, category, token);
    return mode === 'enabled' || (mode === 'auto' && isCapabilitySupportedByModel(input, category, token));
};

const isCapabilityUnverified = (model: ModelRecord, category: OpenAICapabilityOverrideCategory, token: string): boolean => {
    const evidence = model.openaiCapabilityEvidence?.[category];
    const entry = isJsonObject(evidence) ? evidence[token] : null;
    return isJsonObject(entry) && entry['status'] === 'unknown';
};

const resolveEffectiveModalities = (input: OpenAICapabilityRenderInput, manifest: JsonObject): ReadonlySet<string> => {
    const visibleModalities = resolveVisibleModalities(input, manifest);
    const effective = new Set<string>();
    for (const token of visibleModalities) {
        if (isCapabilityEffective(input, 'modalities', token)) {
            effective.add(token);
        }
    }
    effective.add('text');
    return effective;
};

const isCapabilityRequirementMet = (input: OpenAICapabilityRenderInput, requirement: OpenAICapabilityRequirement, effectiveModalities: ReadonlySet<string>): boolean => {
    if (requirement.category === 'modalities') {
        return effectiveModalities.has(requirement.token);
    }
    return isCapabilityEffective(input, requirement.category, requirement.token);
};

const resolveCapabilityRowState = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string, effectiveModalities: ReadonlySet<string>): OpenAICapabilityRowState => {
    const mode = resolveOpenAICapabilityOverrideMode(input.state.current, category, token);
    const baseSupported = isCapabilitySupportedByModel(input, category, token);
    if (category === 'modalities' && token === 'text') {
        return { mode, autoSupported: true, lockedReason: i18n.t('modelDetail.cards.capabilities.lockedReasons.text') };
    }
    const requirement = resolveOpenAICapabilityRequirement(category, token);
    const requirementMet = requirement === null || isCapabilityRequirementMet(input, requirement, effectiveModalities);
    const requirementAvailable = requirement === null || (requirement.category === 'modalities' ? extractPluginModalities(input.plugin).includes(requirement.token) : isOpenAICapabilityEnabled(getPluginOpenAIRecord(input.plugin), requirement.category, requirement.token));
    return { mode, autoSupported: baseSupported && requirementMet, lockedReason: requirement && !requirementAvailable ? requirement.reason : null };
};

const resolveModeLabel = (mode: OpenAICapabilityOverrideMode, autoSupported: boolean): string => {
    switch (mode) {
        case 'auto':
            return autoSupported ? i18n.t('modelDetail.cards.capabilities.modes.autoOn') : i18n.t('modelDetail.cards.capabilities.modes.autoOff');
        case 'enabled':
            return i18n.t('modelDetail.cards.capabilities.modes.enabled');
        case 'disabled':
            return i18n.t('modelDetail.cards.capabilities.modes.disabled');
    }
};

const renderCapabilityRow = (input: OpenAICapabilityRenderInput, category: OpenAICapabilityOverrideCategory, token: string, row: OpenAICapabilityRowState): string => {
    if (!isSafeOpenAICapabilityToken(token) || !isSafeOpenAICapabilityToken(category)) {
        return '';
    }
    const { mode, autoSupported, lockedReason } = row;
    const dirty = mode !== resolveOpenAICapabilityOverrideMode(input.state.original, category, token);
    const requirement = resolveOpenAICapabilityRequirement(category, token);
    const advertised = isCapabilityAdvertisedByModel(input.model, category, token);
    const reason = category === 'modalities' && token === 'text' ? lockedReason : [!advertised ? i18n.t('modelDetail.cards.capabilities.lockedReasons.unsupported') : null, requirement ? requirement.reason : null].filter(Boolean).join(' ');
    const reasonHtml = reason ? `<div class="openai-capability-reason">${escapeHtml(reason)}</div>` : '';
    const unverifiedHtml = isCapabilityUnverified(input.model, category, token) ? `<span class="openai-capability-evidence" data-tooltip="${escapeAttribute(i18n.t('modelDetail.cards.capabilities.unverifiedHint'))}">${escapeHtml(i18n.t('modelDetail.cards.capabilities.unverified'))}</span>` : '';
    const label = input.host.resolveOpenAICapabilityLabel(category, token);
    const toggle = renderToggleSwitch({
        id: `openai-capability-${category}-${token}`,
        checked: mode === 'enabled' || (mode === 'auto' && autoSupported),
        disabled: Boolean(lockedReason),
        labels: { trueLabel: i18n.t('modelDetail.cards.capabilities.modes.enabled'), falseLabel: i18n.t('modelDetail.cards.capabilities.modes.disabled') },
        showLabel: false,
        ariaLabel: label,
        title: resolveModeLabel(mode, autoSupported),
        wrapperClassName: 'openai-capability-mode',
        wrapperDataset: { action: EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY, category, token, mode, autoSupported: String(autoSupported), toggleLocked: String(Boolean(lockedReason)) }
    });
    return `<div class="openai-capability-row setting-change-surface${dirty ? ' modified' : ''}${mode !== 'auto' ? ' is-overridden' : ''}${lockedReason ? ' is-locked' : ''}">
        <div class="openai-capability-meta">
            <div class="openai-capability-label">
                <span class="openai-capability-name">${escapeHtml(label)}</span>
                ${unverifiedHtml}
            </div>
            ${reasonHtml}
        </div>
        ${toggle}
    </div>`;
};

const renderOpenAICapabilityOverrides = (input: OpenAICapabilityRenderInput): string => {
    if (!input.manifest || !input.model.openaiBaseProfile) {
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
            rows.push(renderCapabilityRow(input, category, token, resolveCapabilityRowState(input, category, token, effectiveModalities)));
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
