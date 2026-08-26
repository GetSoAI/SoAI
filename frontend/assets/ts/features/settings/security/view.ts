/* SoAI - Settings security audit view [frontend/assets/ts/features/settings/security/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import type { SettingsStatusBadgeTone } from '@core/settings/contracts.ts';
import { renderSection, renderSettingItem, renderSettingsGroup, renderSettingsRecordList, renderSettingsStatusBadge, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { renderSettingControlMarkup } from '@features/settings/configControlDescriptors.ts';
import { formatSettingLabel, formatSettingPathSegments } from '@features/settings/actions.ts';
import { SECURITY_ACTION_OPEN_USERS } from '@features/settings/security/actions.ts';
import type { SecurityHardeningAudit, SecurityHardeningFinding } from '@core/api/contracts/systemContracts.ts';
import { renderSettingsCapabilityNotice, resolveSettingsCapabilityMessage, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';

interface SecurityAuditSummaryState {
    label: string;
    tone: SettingsStatusBadgeTone;
    help: string;
}

const getConfigValueAtPath = (config: JsonObject, path: string): JsonValue => {
    let current: JsonValue = config;
    for (const part of path.split('.')) {
        if (!isJsonObject(current)) {
            return null;
        }
        const nested: JsonValue | undefined = current[part];
        if (nested === undefined) {
            return null;
        }
        current = nested;
    }
    return current;
};

const renderFindingReferences = (finding: SecurityHardeningFinding): string => {
    const references = finding.configKeys.concat(finding.workspaceReferences);
    if (references.length === 0) {
        return '';
    }
    return `<div class="settings-security-finding-references">${references.map((reference) => `<span class="ui-model-type-badge ${getBadgeColorClass(reference)}">${securityApi.escapeHtml(reference)}</span>`).join('')}</div>`;
};

const renderFinding = (finding: SecurityHardeningFinding): string => {
    return `<div class="settings-record-item setting-change-surface is-invalid settings-security-finding"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${securityApi.escapeHtml(finding.issueId)}</span></div><div class="settings-record-description">${securityApi.escapeHtml(finding.message)}</div>${renderFindingReferences(finding)}</div></div>`;
};

const resolveSummaryState = (audit: SecurityHardeningAudit | null, availability: SettingsCapabilityAvailability): SecurityAuditSummaryState => {
    if (audit === null) {
        const availabilityMessage = resolveSettingsCapabilityMessage(availability);
        if (availabilityMessage !== null) {
            return {
                label: i18n.t('common.notAvailable'),
                tone: 'neutral',
                help: availabilityMessage
            };
        }
        return {
            label: i18n.t('settings.security.pendingBadge'),
            tone: 'neutral',
            help: i18n.t('settings.security.loading')
        };
    }
    const secure = audit.secure;
    return {
        label: secure ? i18n.t('settings.security.secureBadge') : i18n.t('settings.security.warningBadge'),
        tone: secure ? 'active' : 'warning',
        help: secure ? i18n.t('settings.security.secureHelp') : i18n.t('settings.security.findingsHelp', { count: audit.issueCount })
    };
};

const configLabel = (path: string): string => {
    const lastSegment = path.split('.').pop() ?? path;
    return securityApi.escapeHtml(formatSettingLabel(lastSegment));
};

const configHelp = (): string => {
    return securityApi.escapeHtml(i18n.t('settings.security.configHelp'));
};

const renderConfigItem = (config: JsonObject, path: string): string => {
    const value = getConfigValueAtPath(config, path);
    return renderSettingItem({
        label: configLabel(path),
        help: configHelp(),
        control: renderSettingControlMarkup(value, path, 'security'),
        className: 'settings-security-config-item',
        dataset: { path }
    });
};

const renderWorkspaceItem = (): string => {
    const buttonLabel = i18n.t('settings.security.openUsers');
    return `<div class="setting-item settings-security-workspace-item"><div class="setting-info"><span class="setting-help">${securityApi.escapeHtml(i18n.t('settings.security.workspaceHelp'))}</span></div><div class="setting-control"><button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${SECURITY_ACTION_OPEN_USERS}" aria-label="${securityApi.escapeAttribute(buttonLabel)}" data-tooltip="${securityApi.escapeAttribute(buttonLabel)}">${securityApi.escapeHtml(buttonLabel)}</button></div></div>`;
};

const renderSecureState = (): string => {
    return renderEmptyState({ title: i18n.t('settings.security.secureMessage'), className: 'ui-empty-state--simple' }).html;
};

const renderFindingsList = (audit: SecurityHardeningAudit): string => {
    return renderSettingsRecordList({
        className: 'settings-security-findings',
        items: audit.findings.map(renderFinding),
        empty: renderSecureState()
    });
};

const renderFindingsSubgroup = (audit: SecurityHardeningAudit): string => {
    return renderSettingsSubgroup({
        title: i18n.t('settings.security.findingsTitle'),
        description: i18n.t('settings.security.findingsHelp', { count: audit.issueCount }),
        content: renderFindingsList(audit)
    });
};

const configGroupTitle = (parentSegments: readonly string[]): string => {
    if (parentSegments.length === 0) {
        return i18n.t('settings.security.remediationTitle');
    }
    return securityApi.escapeHtml(formatSettingPathSegments(parentSegments));
};

const groupConfigItemsByParent = (config: JsonObject, paths: readonly string[]): Map<string, string[]> => {
    const grouped = new Map<string, string[]>();
    for (const path of paths) {
        const segments = path.split('.');
        const parentKey = segments.slice(0, -1).join('.');
        const item = renderConfigItem(config, path);
        const existing = grouped.get(parentKey);
        if (existing) {
            existing.push(item);
        } else {
            grouped.set(parentKey, [item]);
        }
    }
    return grouped;
};

const renderConfigSubgroups = (audit: SecurityHardeningAudit, config: JsonObject): string => {
    const grouped = groupConfigItemsByParent(config, audit.configKeys);
    const subgroups: string[] = [];
    grouped.forEach((items, parentKey) => {
        subgroups.push(
            renderSettingsSubgroup({
                title: configGroupTitle(parentKey === '' ? [] : parentKey.split('.')),
                content: renderSettingsGroup(items, { className: 'settings-security-group' })
            })
        );
    });
    return subgroups.join('');
};

const renderWorkspaceSubgroup = (audit: SecurityHardeningAudit): string => {
    if (audit.workspaceReferences.length === 0) {
        return '';
    }
    return renderSettingsSubgroup({
        title: securityApi.escapeHtml(i18n.t('settings.security.workspaceTitle')),
        content: renderSettingsGroup([renderWorkspaceItem()], { className: 'settings-security-group' })
    });
};

const renderRemediationSubgroups = (audit: SecurityHardeningAudit, config: JsonObject): string => {
    return `${renderConfigSubgroups(audit, config)}${renderWorkspaceSubgroup(audit)}`;
};

const renderAuditContent = (audit: SecurityHardeningAudit | null, config: JsonObject, availability: SettingsCapabilityAvailability): string => {
    if (audit === null) {
        if (availability.status !== 'pending') {
            return '';
        }
        return renderEmptyState({ title: i18n.t('settings.security.loading'), className: 'ui-empty-state--simple' }).html;
    }
    if (audit.secure) {
        return renderSecureState();
    }
    return `${renderFindingsSubgroup(audit)}${renderRemediationSubgroups(audit, config)}`;
};

const renderSecurityAudit = (audit: SecurityHardeningAudit | null, config: JsonObject, availability: SettingsCapabilityAvailability): string => {
    const { label, tone, help } = resolveSummaryState(audit, availability);
    return renderSection({
        title: securityApi.escapeHtml(i18n.t('settings.security.auditTitle')),
        description: help,
        trailing: tone === 'warning' ? '' : renderSettingsStatusBadge(label, tone),
        className: 'settings-section--security',
        content: `${renderSettingsCapabilityNotice(availability)}${renderAuditContent(audit, config, availability)}`
    });
};

export { renderSecurityAudit };
