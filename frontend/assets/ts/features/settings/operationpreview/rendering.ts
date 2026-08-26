/* SoAI - Settings operation preview rendering [frontend/assets/ts/features/settings/operationpreview/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi } from '@core/security/public.ts';
import type { OperationDryRunPayload } from '@core/tasks/operationPayloads.ts';

interface SettingsOperationPreviewLabels {
    summary: string;
    effects: string;
    warnings: string;
    commands: string;
    emptyEffects: string;
    emptyWarnings: string;
    emptyCommands: string;
}

const renderSettingsOperationPreview = (payload: OperationDryRunPayload, labels: SettingsOperationPreviewLabels): string => {
    return `<div class="settings-operation-preview">` + `<div class="settings-operation-preview__summary">${securityApi.escapeHtml(labels.summary)}</div>` + renderListSection(labels.effects, payload.predictedEffects, labels.emptyEffects, 'settings-operation-preview__effects') + renderListSection(labels.warnings, payload.warnings, labels.emptyWarnings, 'settings-operation-preview__warnings') + renderCommandSection(payload.plannedCommands, labels.commands, labels.emptyCommands) + `</div>`;
};

const renderSettingsOperationPreviewMessage = (message: string): string => `<div class="settings-operation-preview"><div class="settings-operation-preview__summary">${securityApi.escapeHtml(message)}</div></div>`;

const renderCommandSection = (commands: readonly string[], label: string, emptyLabel: string): string => {
    const commandBody = commands.length > 0 ? commands.map((command) => `<div class="settings-operation-preview__code-line">${securityApi.escapeHtml(command)}</div>`).join('') : securityApi.escapeHtml(emptyLabel);
    return renderPreviewSection(label, `<div class="settings-operation-preview__code">${commandBody}</div>`);
};

const renderListSection = (label: string, values: readonly string[], emptyLabel: string, className: string): string => {
    const content = values.length > 0 ? `<ul class="${securityApi.escapeAttribute(className)}">${values.map((value) => `<li>${securityApi.escapeHtml(value)}</li>`).join('')}</ul>` : `<div class="settings-operation-preview__empty">${securityApi.escapeHtml(emptyLabel)}</div>`;
    return renderPreviewSection(label, content);
};

const renderPreviewSection = (label: string, content: string): string => `<section class="settings-operation-preview__section"><div class="settings-operation-preview__label">${securityApi.escapeHtml(label)}</div>${content}</section>`;

export { renderSettingsOperationPreview, renderSettingsOperationPreviewMessage };
export type { SettingsOperationPreviewLabels };
