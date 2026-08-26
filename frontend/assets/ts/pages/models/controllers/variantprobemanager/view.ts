/* SoAI - Models page variant probe manager rendering [frontend/assets/ts/pages/models/controllers/variantprobemanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelVariantResponse, ModelVariantSpeedTest } from '@core/api/contracts/modelVariantContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import type { DisplayResult } from '@core/speedTest.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { VariantProbeRenderContext } from '@pages/models/controllers/variantprobemanager/types.ts';

type FitState = 'true' | 'false' | 'unknown';

const resolveFitState = (value: boolean | null): FitState => {
    if (value === true) return 'true';
    if (value === false) return 'false';
    return 'unknown';
};

export const getVariantCombinedFitValue = (variant: ModelVariantResponse | null): { found: boolean; value: boolean | null } => {
    return variant ? { found: true, value: variant.vramRamFit } : { found: false, value: null };
};

export const getVariantAdvisoryTone = (variant: ModelVariantResponse | null): string => {
    if (!variant) return 'variant-check-advisory--neutral';
    const combined = getVariantCombinedFitValue(variant);
    const runnable = variant.runnable;
    const vramFit = variant.vramFit;
    const diskFit = variant.diskFit;
    const hasFailure = runnable === false || vramFit === false || diskFit === false || (combined.found && combined.value === false);

    if (hasFailure) return 'variant-check-advisory--warn';
    if (runnable === true) return 'variant-check-advisory--ok';
    return 'variant-check-advisory--neutral';
};

const buildVariantBadgeIcon = (context: VariantProbeRenderContext, iconName: IconName, size: number): string => {
    const strokeWidth = iconName === 'clock' ? 1.7 : size === 12 ? 1 : 1.5;
    return context.host.getIconSync(iconName, { size, strokeWidth }).html;
};

const resolveFitLabelText = (type: 'disk' | 'vram' | 'vram-ram', state: FitState): string => {
    if (type === 'disk') {
        switch (state) {
            case 'true':
                return i18n.t('models.modal.addModel.variantCheck.diskFitTrue');
            case 'false':
                return i18n.t('models.modal.addModel.variantCheck.diskFitFalse');
            default:
                return i18n.t('models.modal.addModel.variantCheck.diskFitUnknown');
        }
    }
    if (type === 'vram') {
        switch (state) {
            case 'true':
                return i18n.t('models.modal.addModel.variantCheck.vramFitTrue');
            case 'false':
                return i18n.t('models.modal.addModel.variantCheck.vramFitFalse');
            default:
                return i18n.t('models.modal.addModel.variantCheck.vramFitUnknown');
        }
    }
    switch (state) {
        case 'true':
            return i18n.t('models.modal.addModel.variantCheck.vramRamFitTrue');
        case 'false':
            return i18n.t('models.modal.addModel.variantCheck.vramRamFitFalse');
        default:
            return i18n.t('models.modal.addModel.variantCheck.vramRamFitUnknown');
    }
};

const resolveFitShortLabelText = (type: 'disk' | 'vram' | 'vram-ram'): string => {
    switch (type) {
        case 'disk':
            return i18n.t('models.modal.addModel.variantCheck.diskLabel');
        case 'vram':
            return i18n.t('models.modal.addModel.variantCheck.vramLabel');
        default:
            return i18n.t('models.modal.addModel.variantCheck.vramRamLabel');
    }
};

export const buildVariantFitBadge = (context: VariantProbeRenderContext, type: string, value: boolean | null): string => {
    if (type !== 'disk' && type !== 'vram' && type !== 'vram-ram') return '';
    const state = resolveFitState(value);
    const label = resolveFitLabelText(type, state);
    const iconName = value === true ? 'success-modal' : value === false ? 'danger-modal' : 'warning-modal';
    const badgeClass = value === true ? 'variant-check-badge--ok' : value === false ? 'variant-check-badge--fail' : 'variant-check-badge--neutral';
    const textLabel = resolveFitShortLabelText(type);
    const textMarkup = textLabel ? `<span class="variant-check-badge-text">${context.sanitizer.html(textLabel)}</span>` : '';

    const iconMarkup = buildVariantBadgeIcon(context, iconName, 12);
    const icon = iconMarkup ? `<span class="variant-check-badge-icon" aria-hidden="true">${iconMarkup}</span>` : '';
    return `<span class="variant-check-badge ${badgeClass}" ${renderLabelAttributes(label)} role="img">${icon}${textMarkup}</span>`;
};

export const buildVariantRunnableBadge = (context: VariantProbeRenderContext, value: boolean | null): string => {
    const state = resolveFitState(value);
    const label = state === 'true' ? i18n.t('models.modal.addModel.variantCheck.runnableTrue') : state === 'false' ? i18n.t('models.modal.addModel.variantCheck.runnableFalse') : i18n.t('models.modal.addModel.variantCheck.runnableUnknown');
    const badgeClass = value === true ? 'variant-check-badge--ok' : value === false ? 'variant-check-badge--warn' : 'variant-check-badge--neutral';
    const iconName = value === true ? 'success-modal' : 'warning-modal';
    const iconMarkup = buildVariantBadgeIcon(context, iconName, 12);
    const icon = iconMarkup ? `<span class="variant-check-badge-icon" aria-hidden="true">${iconMarkup}</span>` : '';
    return `<span class="variant-check-badge ${badgeClass}" ${renderLabelAttributes(label)}>${icon}<span class="variant-check-badge-text">${context.sanitizer.html(label)}</span></span>`;
};

const buildVariantTimingBadge = (context: VariantProbeRenderContext, timingType: 'download' | 'load', display: DisplayResult | null, source: ModelVariantSpeedTest | null): string => {
    if (!display || !display.estimateLabel.trim()) return '';
    const estimateLabel = display.estimateLabel;
    const throughputLabel = display.throughputLabel;
    const estimateSeconds = display.estimateMs === null ? null : display.estimateMs / 1000;
    const isDownload = timingType === 'download';
    const estimateTitle = isDownload ? i18n.t('models.modal.addModel.variantCheck.downloadEstimate') : i18n.t('models.modal.addModel.variantCheck.loadEstimate');
    const modeLabel = isDownload ? i18n.t('models.modal.addModel.variantCheck.networkLabel') : i18n.t('models.modal.addModel.variantCheck.diskLabel');
    const tooltipItems: string[] = [];
    tooltipItems.push(estimateTitle);
    if (isDownload) {
        tooltipItems.push(i18n.t('models.modal.addModel.variantCheck.estimatedDownloadTime', { value: estimateLabel }));
    } else {
        tooltipItems.push(i18n.t('models.modal.addModel.variantCheck.estimatedLoadTime', { value: estimateLabel }));
    }
    if (isString(throughputLabel) && throughputLabel.trim()) tooltipItems.push(throughputLabel.trim());
    if (modeLabel) tooltipItems.push(modeLabel);
    const sample = context.speedTest?.formatSample?.(source);
    if (isString(sample) && sample.trim()) tooltipItems.push(sample.trim());
    if (!isDownload) {
        const lf = context.speedTest?.getLoadFactor?.(source);
        if (isNumber(lf) && Number.isFinite(lf) && lf !== 1) {
            const fmtLoad = context.formatDecimal(lf);
            if (fmtLoad) tooltipItems.push(i18n.t('models.modal.addModel.variantCheck.loadFactor', { value: fmtLoad }));
        }
    }
    const tooltip = tooltipItems.join(' • ');
    const badgeClass = isDownload && isNumber(estimateSeconds) && estimateSeconds > 3600 ? 'variant-check-badge--warn' : 'variant-check-badge--ok';
    const iconMarkup = buildVariantBadgeIcon(context, 'clock', 12);
    const icon = iconMarkup ? `<span class="variant-check-badge-icon" aria-hidden="true">${iconMarkup}</span>` : '';
    const text = isDownload ? i18n.t('models.modal.addModel.variantCheck.estimatedDownloadTime', { value: estimateLabel }) : i18n.t('models.modal.addModel.variantCheck.estimatedLoadTime', { value: estimateLabel });
    return `<span class="variant-check-badge ${badgeClass}" ${renderLabelAttributes(tooltip)}>${icon}<span class="variant-check-badge-text">${context.sanitizer.html(text)}</span></span>`;
};

const resolveVariantSpeedTestDisplay = (context: VariantProbeRenderContext, source: ModelVariantSpeedTest | null): DisplayResult | null => {
    return context.speedTest?.getDisplay?.(source) ?? null;
};

export const buildVariantMetaBadge = (context: VariantProbeRenderContext, label: string | null): string => {
    return label ? `<span class="variant-check-badge variant-check-badge--meta">${context.sanitizer.html(String(label))}</span>` : '';
};

export const buildVariantCheckEntry = (variant: ModelVariantResponse | null, index: number, context: VariantProbeRenderContext): string => {
    if (!variant) return '';
    const escape = (value: string | number | boolean | null): string => context.sanitizer.html(value);
    const rawName = variant.normalizedName || variant.name || variant.id || i18n.t('models.types.unknown');
    const nameText = String(rawName ?? '');
    const name = escape(nameText);
    const quantization = variant.quantization;
    const quant = isString(quantization) && quantization.trim();
    const quantHtml = quant ? `<span class="variant-check-entry-quant">${escape(i18n.t('models.modal.addModel.quantLabel'))}: ${escape(quant.trim())}</span>` : '';

    const metrics: string[] = [];
    const pushMetric = (label: string, value: string | number): number => metrics.push(`<span class="variant-check-metric">${escape(label)}: ${escape(value)}</span>`);

    const sizeBytes = variant.sizeBytes;
    const sizeGb = variant.sizeGb;
    const ramRequiredGb = variant.ramRequiredGb;
    const vramRequiredGb = variant.vramRequiredGb;
    if (isNumber(sizeBytes) && Number.isFinite(sizeBytes) && sizeBytes > 0) {
        pushMetric(i18n.t('models.modal.addModel.variantCheck.size'), formatBytes(sizeBytes));
    } else if (isNumber(sizeGb) && Number.isFinite(sizeGb)) {
        const fmt = context.formatDecimal(sizeGb);
        if (fmt) pushMetric(i18n.t('models.modal.addModel.variantCheck.size'), i18n.t('models.modal.addModel.variantCheck.valueGb', { value: fmt }));
    }
    if (isNumber(ramRequiredGb) && Number.isFinite(ramRequiredGb)) {
        const fmt = context.formatDecimal(ramRequiredGb);
        if (fmt) pushMetric(i18n.t('models.modal.addModel.variantCheck.memory'), i18n.t('models.modal.addModel.variantCheck.valueGb', { value: fmt }));
    }
    if (isNumber(vramRequiredGb) && Number.isFinite(vramRequiredGb)) {
        const fmt = context.formatDecimal(vramRequiredGb);
        if (fmt) pushMetric(i18n.t('models.modal.addModel.variantCheck.vram'), i18n.t('models.modal.addModel.variantCheck.valueGb', { value: fmt }));
    }
    const metricsHtml = metrics.length ? `<div class="variant-check-metrics">${metrics.join('')}</div>` : '';

    const branchBadges: string[] = [];
    const fam = variant.family;
    const familyLabel = isString(fam) ? fam.trim() : '';
    if (familyLabel) {
        branchBadges.push(buildVariantMetaBadge(context, familyLabel.toUpperCase()));
    }
    const metaHtml = branchBadges.length ? `<div class="variant-check-meta">${branchBadges.join('')}</div>` : '';

    const combinedFit = getVariantCombinedFitValue(variant);
    const diskFit = variant.diskFit;
    const vramFit = variant.vramFit;
    const runnable = variant.runnable;
    const networkSpeedTest = variant.networkSpeedTest;
    const speedTest = variant.speedTest;
    const fitBadges = [buildVariantFitBadge(context, 'disk', diskFit), buildVariantFitBadge(context, 'vram', vramFit), combinedFit.found ? buildVariantFitBadge(context, 'vram-ram', combinedFit.value) : '', buildVariantRunnableBadge(context, runnable), buildVariantTimingBadge(context, 'download', resolveVariantSpeedTestDisplay(context, networkSpeedTest), networkSpeedTest), buildVariantTimingBadge(context, 'load', resolveVariantSpeedTestDisplay(context, speedTest), speedTest)].filter(Boolean);
    const fitHtml = fitBadges.length ? `<div class="variant-check-badges">${fitBadges.join('')}</div>` : '';

    const summaries: string[] = [];
    summaries.push(resolveFitLabelText('disk', resolveFitState(diskFit)));
    if (combinedFit.found) summaries.push(resolveFitLabelText('vram-ram', resolveFitState(combinedFit.value)));
    summaries.push(runnable === true ? i18n.t('models.modal.addModel.variantCheck.runnableTrue') : runnable === false ? i18n.t('models.modal.addModel.variantCheck.runnableFalse') : i18n.t('models.modal.addModel.variantCheck.runnableUnknown'));
    const variantAdvisory = variant.advisory;
    const advisoryText = (isString(variantAdvisory) && variantAdvisory.trim()) || summaries.join(' • ') || i18n.t('models.modal.addModel.variantCheck.title');

    const hardwareCompatibility = variant.hardwareCompatibility;
    const hardwareCompatibilityLabel = variant.hardwareCompatibilityLabel;
    const compKey = isString(hardwareCompatibility) ? hardwareCompatibility.trim().toLowerCase() : '';
    let compLabel = isString(hardwareCompatibilityLabel) ? hardwareCompatibilityLabel.trim() : '';
    if (compKey === 'gpu_only') compLabel = i18n.t('models.modal.addModel.variantCheck.hardwareCompatibility.gpuOnly');
    else if (compKey === 'cpu_gpu') compLabel = i18n.t('models.modal.addModel.variantCheck.hardwareCompatibility.cpuGpu');

    const tone = getVariantAdvisoryTone(variant);
    const conclusion = tone === 'variant-check-advisory--ok' ? i18n.t('models.modal.addModel.variantCheck.conclusionOk') : tone === 'variant-check-advisory--warn' ? i18n.t('models.modal.addModel.variantCheck.conclusionWarn') : '';

    const segments: string[] = [];
    if (advisoryText) segments.push(`<span class="variant-check-advisory-text">${escape(advisoryText)}</span>`);

    if (tone === 'variant-check-advisory--ok' && diskFit === true) {
        const diskRem = context.formatDecimal(variant.diskRemainingGb);
        if (diskRem) {
            segments.push(`<span class="variant-check-remaining">${escape(i18n.t('models.modal.addModel.variantCheck.diskRemaining', { value: diskRem }))}</span>`);
        }
    }
    if (compLabel) segments.push(`<span class="variant-check-compatibility">${escape(i18n.t('models.modal.addModel.variantCheck.hardwareCompatibility.label'))}: ${escape(compLabel)}.</span>`);
    if (conclusion) {
        const icon = tone === 'variant-check-advisory--ok' ? '✓' : '×';
        segments.push(`<span class="variant-check-conclusion"><span class="variant-check-conclusion-icon" aria-hidden="true">${icon}</span><strong>${escape(conclusion)}</strong></span>`);
    }

    let advisoryHtml = '';
    if (segments.length) {
        const advisoryIconMarkup = buildVariantBadgeIcon(context, 'model-default', 48);
        const icon = advisoryIconMarkup ? `<span class="variant-check-advisory-icon" aria-hidden="true">${advisoryIconMarkup}</span>` : '';
        const content = segments.map((entry, index) => (index < segments.length - 1 ? `- ${entry}` : entry)).join('<br>');
        advisoryHtml = `<div class="variant-check-advisory ${tone}"><div class="variant-check-advisory-content"><div class="variant-check-advisory-header">${escape(i18n.t('models.modal.addModel.variantCheck.reportHeader'))}</div>${content}</div>${icon}</div>`;
    }

    const entryClass = Number.isInteger(context.selectedIndex) && index === context.selectedIndex ? 'variant-check-entry variant-check-entry--selected' : 'variant-check-entry';
    return `
        <div class="${entryClass}" data-variant-index="${index}" role="button" tabindex="0" ${renderLabelAttributes(nameText)}>
        <div class="variant-check-entry-header">
        <div class="variant-check-entry-title">
        <span class="variant-check-entry-name">${name}</span>
        ${quantHtml}
        </div>
        ${metricsHtml}
        </div>
        ${metaHtml}
        ${fitHtml}
        ${advisoryHtml}
        </div>
        `.trim();
};
