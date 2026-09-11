/* SoAI - Plugins page compatibility controller [frontend/assets/ts/pages/plugins/controllers/pluginsCompatibilityController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString, toTrimmedUpper } from '@core/normalize.ts';
import { isArray, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { CircuitBreakerInfo, CompatibilityInfo } from '@features/catalog/public.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface PluginsCompatibilityControllerHost extends PageFeedbackOwnerHost {
    resolvePluginRecord(plugin: PluginRecord | string | null | undefined): PluginRecord | null;
    getPluginCompatibility(plugin: PluginRecord | string | null | undefined): CompatibilityInfo;
    sanitizeText(value: JsonValue, options?: Record<string, JsonValue>): string;
    sanitizeCompatibilityMessage(value: JsonValue): string;
    isCircuitBreakerActive(plugin: PluginRecord | string | null | undefined): boolean;
}

type CompatibilityMessagePresentation = 'full' | 'overrideNotice' | 'card';

class PluginsCompatibilityController {
    #host: PluginsCompatibilityControllerHost;

    constructor(host: PluginsCompatibilityControllerHost) {
        this.#host = host;
    }

    formatCompatibilityList(values: ReadonlyArray<JsonValue | undefined>, normalization: 'uppercase' | 'preserve' = 'uppercase'): string {
        if (!isArray(values)) {
            throw new Error('Compatibility list requires an array of values');
        }
        const items = values.map((value: JsonValue | undefined): string => (normalization === 'uppercase' ? toTrimmedUpper(value) : toTrimmedString(value))).filter(Boolean);
        if (!items.length) {
            throw new Error('Compatibility list is empty');
        }
        return items.join(', ');
    }

    resolveCompatibilityMessage(compatibility: CompatibilityInfo | null | undefined, presentation: CompatibilityMessagePresentation = 'full'): string {
        if (!compatibility || compatibility.isCompatible) {
            return '';
        }
        const detailsObject = isObject(compatibility.details) ? compatibility.details : {};
        const getVersionPair = (): { required: string; current: string } => {
            const requiredVersion = detailsObject['requiredVersion'];
            const detectedVersion = detailsObject['detectedVersion'];
            const required = isString(requiredVersion) ? requiredVersion.trim() : '';
            const current = isString(detectedVersion) ? detectedVersion.trim() : '';
            if (!required || !current) {
                throw new Error(`Incompatibility missing details: ${JSON.stringify({ details: detailsObject, reason: compatibility.reason })}`);
            }
            return { required, current };
        };
        const sanitizeCompatibilityMessage = this.#host.sanitizeCompatibilityMessage;
        const useCompactHardware = presentation !== 'full' && compatibility.canOverride === true;

        switch (compatibility.reason) {
            case 'VERSION_INCOMPATIBLE': {
                const versionPair = getVersionPair();
                if (useCompactHardware) {
                    return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.hardwareShort', versionPair));
                }
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.version', versionPair));
            }
            case 'OS_INCOMPATIBLE': {
                const detected = toTrimmedUpper(detailsObject['detectedOs']);
                if (!detected) {
                    throw new Error(`OS compatibility message missing detected OS: ${JSON.stringify({ details: detailsObject, reason: compatibility.reason })}`);
                }
                const requiredOsCandidate = detailsObject['requiredOs'];
                const requiredOs = isArray(requiredOsCandidate) ? requiredOsCandidate : [requiredOsCandidate];
                if (!requiredOs.length || requiredOs.every((value: JsonValue | undefined): boolean => !String(value ?? '').trim())) {
                    throw new Error(`OS compatibility message missing required OS: ${JSON.stringify({ details: detailsObject, reason: compatibility.reason })}`);
                }
                const required = this.formatCompatibilityList(requiredOs);
                if (useCompactHardware) {
                    if (presentation === 'card') {
                        return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.osCard', { required, detected }));
                    }
                    return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.osShort', { required, detected }));
                }
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.os', { required, detected }));
            }
            case 'GPU_REQUIRED': {
                const requiredGpuCandidate = detailsObject['requiredGpu'];
                const detectedVendorsCandidate = detailsObject['detectedVendors'];
                const requiredGpu = isArray(requiredGpuCandidate) ? requiredGpuCandidate : [requiredGpuCandidate];
                const detectedVendors = isArray(detectedVendorsCandidate) ? detectedVendorsCandidate : [detectedVendorsCandidate];
                if (!requiredGpu.length || requiredGpu.every((value: JsonValue | undefined): boolean => !String(value ?? '').trim())) {
                    throw new Error(`GPU compatibility message missing required GPU: ${JSON.stringify({ details: detailsObject, reason: compatibility.reason })}`);
                }
                const detectedGpu = detectedVendors.length && !detectedVendors.every((value: JsonValue | undefined): boolean => !String(value ?? '').trim()) ? this.formatCompatibilityList(detectedVendors) : i18n.t('plugins.compatibility.noneDetected');
                if (useCompactHardware) {
                    return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.gpuShort', { required: this.formatCompatibilityList(requiredGpu), detected: detectedGpu }));
                }
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.gpu', { required: this.formatCompatibilityList(requiredGpu), detected: detectedGpu }));
            }
            case 'BROKEN_PLUGIN': {
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.broken'));
            }
            case 'DEPENDENCY_MISSING': {
                const missingDependencies = detailsObject['missingDependencies'];
                if (!isArray(missingDependencies)) {
                    throw new Error(`Dependency compatibility message missing dependency list: ${JSON.stringify({ details: detailsObject, reason: compatibility.reason })}`);
                }
                const dependencies = this.formatCompatibilityList(missingDependencies, 'preserve');
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.dependencyMissing', { dependencies }));
            }
            default: {
                const directMessage = sanitizeCompatibilityMessage(compatibility.message ?? '');
                if (directMessage) {
                    return directMessage;
                }
                const versionPair = getVersionPair();
                if (useCompactHardware) {
                    return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.reasons.hardwareShort', versionPair));
                }
                return sanitizeCompatibilityMessage(i18n.t('plugins.compatibility.default', versionPair));
            }
        }
    }

    getIncompatibilityContext(plugin: PluginRecord | string | null | undefined, presentation: CompatibilityMessagePresentation): { message: string; iconName: IconName; variant: string } | null {
        const record = this.#host.resolvePluginRecord(plugin);
        const compatibility = this.#host.getPluginCompatibility(record);
        if (!compatibility?.reason || compatibility.isOverridden) {
            return null;
        }
        const message = this.resolveCompatibilityMessage(compatibility, presentation);
        if (!message) {
            return null;
        }
        const icons: Record<string, IconName> = {
            VERSION_INCOMPATIBLE: 'warning',
            OS_INCOMPATIBLE: 'device-cpu',
            GPU_REQUIRED: 'device-gpu',
            BROKEN_PLUGIN: 'error'
        };
        return {
            message,
            iconName: icons[compatibility.reason] ?? 'warning',
            variant: compatibility.canOverride ? 'hardware' : 'fundamental'
        };
    }

    getIncompatibleNotice(plugin: PluginRecord | string | null | undefined): string {
        const context = this.getIncompatibilityContext(plugin, 'card');
        if (!context) {
            return '';
        }
        const message = isString(context.message) ? context.message.trim() : '';
        if (!message) {
            return '';
        }
        const safeMessage = this.#host.sanitizeText(message);
        const icon = context.variant === 'hardware' ? '' : getIconSync(context.iconName, { size: 16, strokeWidth: 1.5 }).html;
        const classes = ['plugin-compatibility-banner', 'incompatible'];
        if (context.variant === 'hardware') {
            classes.push('hardware-incompatible');
        }
        return `<div class="${classes.join(' ')}">${icon ? `${icon}<span> ${safeMessage}</span>` : safeMessage}</div>`;
    }

    getCircuitBreakerNotice(plugin: PluginRecord | string | null | undefined): string {
        const record = this.#host.resolvePluginRecord(plugin);
        if (!record || !this.#host.isCircuitBreakerActive(record)) {
            return '';
        }
        const breaker = record.circuitBreaker;
        if (!breaker) {
            return '';
        }
        const name = record.displayName ?? record.name;
        if (!name) {
            throw new Error(`Circuit breaker plugin is missing a display name: ${JSON.stringify(record)}`);
        }
        const failureCount = breaker.failureCount;
        const message = isFiniteNumber(failureCount) && failureCount > 0 ? i18n.t('plugins.circuit_breaker.banner', { plugin: name, failureCount }) : i18n.t('plugins.circuit_breaker.bannerCountUnavailable', { plugin: name });
        return `<div class="plugin-compatibility-banner circuit-breaker">${this.#host.sanitizeText(message)}</div>`;
    }

    areCircuitBreakerStatesEqual(left: CircuitBreakerInfo | null | undefined, right: CircuitBreakerInfo | null | undefined): boolean {
        if (left === right) {
            return true;
        }
        if (!left || !right) {
            return false;
        }
        if (String(left.state).toLowerCase() !== String(right.state).toLowerCase()) {
            return false;
        }
        return left.isOpen === right.isOpen && left.failureCount === right.failureCount && left.failureThreshold === right.failureThreshold && left.recoveryTimeoutSec === right.recoveryTimeoutSec && left.lastFailureAtMs === right.lastFailureAtMs && left.wasEnabled === right.wasEnabled;
    }

    getPluginIncompatibilityMessage(plugin: PluginRecord | string | null | undefined, { includeName = true }: { includeName?: boolean } = {}): string {
        const context = this.getIncompatibilityContext(plugin, 'overrideNotice');
        const reason = isString(context?.message) ? context.message.trim() : '';
        if (!reason) {
            return '';
        }
        const reasonText = this.#host.sanitizeText(reason);
        if (!includeName) {
            return reasonText;
        }
        const record = this.#host.resolvePluginRecord(plugin);
        const name = record?.displayName ?? record?.name;
        if (!name) {
            throw new Error(`Plugin record missing a name for incompatibility message: ${JSON.stringify(record)}`);
        }
        return i18n.t('plugins.notifications.pluginIncompatibleReason', {
            plugin: this.#host.sanitizeText(name),
            reason: reasonText
        });
    }

    notifyPluginIncompatible(plugin: PluginRecord | string | null | undefined): void {
        const message = this.getPluginIncompatibilityMessage(plugin, { includeName: true });
        if (isString(message) && message.trim()) {
            this.#host.feedback.show(this.#host.sanitizeText(message), 'warning');
        }
    }

    notifyOverrideRequired(plugin: PluginRecord | string | null | undefined): void {
        const record = this.#host.resolvePluginRecord(plugin);
        const name = record?.displayName ?? record?.name;
        if (!name) {
            throw new Error('Override notification requires a plugin name');
        }
        const base = i18n.t('plugins.notifications.overrideRequired', { plugin: name });
        const reason = this.getPluginIncompatibilityMessage(record, { includeName: false });
        this.#host.feedback.show(reason ? `${base} ${reason}` : base, 'warning');
    }
}

export { PluginsCompatibilityController };
export type { PluginsCompatibilityControllerHost };
