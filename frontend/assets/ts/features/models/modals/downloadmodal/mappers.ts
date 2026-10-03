/* SoAI - Model download modal mapping [frontend/assets/ts/features/models/modals/downloadmodal/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { toTrimmedString, toTrimmedUpper } from '@core/normalize.ts';
import { resolveHttpUrl, toTrustedUiHtml } from '@core/security/public.ts';
import type { TrustedHtml } from '@core/security/htmlSanitizer.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginModelRepositoryCatalogEntry, PluginRecord } from '@core/types/pluginTypes.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import type { RepositoryLinkData } from '@features/models/search/modelSearchTypes.ts';

interface RepositoryBadgeHost {
    session: {
        sanitizer: {
            html(value: string): string;
        };
    };
}

const interpolateRepositoryTemplate = (template: string | null | undefined, modelId: string): string => {
    if (!isString(template)) {
        return '';
    }
    const trimmedTemplate = toTrimmedString(template);
    if (!trimmedTemplate) {
        return '';
    }
    const tokens = ['{model}', '{MODEL}', '{model_id}', '{MODEL_ID}', '%s'];
    const hasToken = tokens.some((token) => trimmedTemplate.includes(token));
    if (!hasToken) {
        return trimmedTemplate;
    }
    const normalizedModelId = toTrimmedString(modelId);
    if (!normalizedModelId) {
        return '';
    }
    const encodedModelId = encodeSegment(normalizedModelId);
    return tokens.reduce((value, token) => value.split(token).join(encodedModelId), trimmedTemplate);
};

const deriveRepositoryLabel = (plugin: PluginRecord | null | undefined, entry: PluginModelRepositoryCatalogEntry | null, url: string): string => {
    if (entry?.displayName) return entry.displayName;
    if (entry?.name) return entry.name;
    if (isObject(plugin)) {
        const displayName = plugin.displayName;
        if (isString(displayName) && displayName) {
            return displayName;
        }
        const name = plugin['name'];
        if (isString(name) && name) {
            return name;
        }
    }
    try {
        const resolved = resolveHttpUrl(url) ?? url;
        return new URL(resolved).hostname || url;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Parsing repository URL failed', runtimeError);
    }
    return url;
};

const resolveRepositoryLinkData = (plugin: PluginRecord | null | undefined, modelId: string): RepositoryLinkData | null => {
    if (!isObject(plugin)) {
        return null;
    }
    const modelRepository = plugin.modelRepository;
    if (!modelRepository) {
        return null;
    }
    if (isString(modelRepository)) {
        const repositoryUrl = interpolateRepositoryTemplate(modelRepository, modelId);
        if (!repositoryUrl) {
            return null;
        }
        return {
            url: repositoryUrl,
            label: deriveRepositoryLabel(plugin, null, repositoryUrl),
            badges: []
        };
    }
    const repository = modelRepository;
    const normalizedModelId = toTrimmedString(modelId);
    let matchedEntry: PluginModelRepositoryCatalogEntry | null = null;
    const catalog = repository.catalog;
    if (normalizedModelId && catalog) {
        for (const candidate of catalog) {
            if (candidate.id === normalizedModelId || candidate.name === normalizedModelId || candidate.slug === normalizedModelId) {
                matchedEntry = candidate;
                break;
            }
            if (candidate.aliases?.includes(normalizedModelId)) {
                matchedEntry = candidate;
                break;
            }
        }
    }

    const urlCandidates = [matchedEntry?.repositoryUrl, repository.repositoryUrl, repository.url, repository.baseUrl, repository.link, repository.href];
    let resolvedUrl = '';
    for (const candidate of urlCandidates) {
        const candidateText = isString(candidate) ? toTrimmedString(candidate) : '';
        if (!candidateText) {
            continue;
        }
        resolvedUrl = interpolateRepositoryTemplate(candidateText, normalizedModelId);
        if (resolvedUrl) {
            break;
        }
    }
    if (!resolvedUrl) {
        return null;
    }

    const entryDisplayName = matchedEntry?.displayName ?? '';
    const entryName = matchedEntry?.name ?? '';
    const entryId = matchedEntry?.id ?? '';
    const repositoryDisplayName = isString(repository.displayName) ? repository.displayName : '';
    const repositoryName = repository.name ?? '';
    const label = entryDisplayName || entryName || entryId || repositoryDisplayName || repositoryName || deriveRepositoryLabel(plugin, matchedEntry, resolvedUrl);

    const badges: RepositoryLinkData['badges'] = [];
    if (matchedEntry?.tags) {
        badges.push(...matchedEntry.tags);
    }
    if (repository.tags) {
        badges.push(...repository.tags);
    }

    return { url: resolvedUrl, label, badges };
};

const buildRepositoryBadgesMarkup = (host: RepositoryBadgeHost, plugin: PluginRecord | null | undefined, extraBadges: JsonValue[] | null | undefined): TrustedHtml => {
    const pluginObject = isObject(plugin) ? plugin : null;
    const badges = [...(isArray(extraBadges) ? extraBadges : []), ...(isArray(pluginObject?.modelTypes) ? pluginObject.modelTypes : [])];
    const uniqueBadges = new Set<string>();
    const markup = badges
        .map((badge) => {
            if (!isString(badge)) {
                return '';
            }
            const normalizedBadge = toTrimmedUpper(badge);
            if (!normalizedBadge || uniqueBadges.has(normalizedBadge)) {
                return '';
            }
            uniqueBadges.add(normalizedBadge);
            return `<span dir="auto" class="ui-model-type-badge ${getBadgeColorClass(normalizedBadge)}">${host.session.sanitizer.html(normalizedBadge)}</span>`;
        })
        .filter(Boolean)
        .join('');
    return toTrustedUiHtml(markup);
};

export { buildRepositoryBadgesMarkup, deriveRepositoryLabel, interpolateRepositoryTemplate, resolveRepositoryLinkData };
export type { RepositoryLinkData };
