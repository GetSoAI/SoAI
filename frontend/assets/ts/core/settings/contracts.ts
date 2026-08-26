/* SoAI - Shared settings contracts [frontend/assets/ts/core/settings/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ToggleLabelState } from '@core/toggleSwitch.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type NormalTabRendererId = 'preferences' | 'theme' | 'users' | 'security' | 'licensing' | 'acl' | 'apiKeys' | 'mcp' | 'externalAccounts' | 'backup' | 'system' | 'messaging' | 'product';
type SettingsCapabilityStatus = 'pending' | 'ready' | 'partial' | 'stale' | 'unavailable';
interface SettingsCapabilityAvailability {
    status: SettingsCapabilityStatus;
    updatedAtMs: number | null;
}
type SettingsAttributeValue = string | boolean | null | undefined;
interface NormalTabDefinition {
    id: string;
    rendererId: NormalTabRendererId;
    adminOnly?: boolean;
    osOnly?: boolean;
    actions?: readonly string[];
    getLabel: () => string;
}
interface AdvancedTabDefinition {
    id: string;
    label: string;
    advanced: true;
    sectionKey?: string;
    adminOnly?: boolean;
    osOnly?: boolean;
    actions?: readonly string[];
}
type TabDefinition = NormalTabDefinition | AdvancedTabDefinition;
interface PreferenceToggleConfig {
    id: string;
    notifyKey: string;
    notifyStates: { enabled: string; disabled: string } | null;
    getValue: () => boolean;
    setValue: (value: boolean) => string | boolean | null | undefined;
    externalEvent: { name: string; getValue: (error: CustomEvent) => boolean } | null;
    label: string;
    help: string;
}
interface ExternalEventConfig {
    target?: Window | EventTarget;
    event: string;
    getValue?: (error: Event, element?: Element) => JsonValue | null | undefined;
    handler?: (error: Event, element?: Element, value?: JsonValue | null) => void;
}
interface BindControlOptions {
    id: string;
    type?: string;
    eventType?: string;
    initialValue: JsonValue | null | undefined;
    normalize?: (value: JsonValue | null | undefined, error?: Event) => JsonValue | null | undefined;
    extractValue?: (target: EventTarget, error: Event) => JsonValue | null | undefined;
    onChange?: (value: JsonValue | null | undefined, error: Event, element?: Element) => Promise<void> | void;
    afterChange?: (value: JsonValue | null | undefined, element: Element, error?: Event) => void;
    external?: ExternalEventConfig[];
}
interface ToggleControlOptions {
    id: string;
    checked: boolean;
    labels: ToggleLabelState;
    inline?: boolean;
    disabled?: boolean;
    inputClassName?: string;
    wrapperClassName?: string;
    inputDataset?: Record<string, string>;
    wrapperDataset?: Record<string, string>;
    showLabel?: boolean;
}
interface SelectControlOptions {
    id: string;
    options: Array<{ value: string | number | null; label: string; disabled?: boolean }>;
    selected: string | number | null | undefined;
    disabled?: boolean;
    wide?: boolean;
    compact?: boolean;
}
interface SliderControlOptions {
    id: string;
    valueId: string;
    min: number;
    max: number;
    step: number;
    value: number;
    valueLabel: string;
}
interface SettingItemOptions {
    label: string;
    help?: string;
    control: string;
    className?: string;
    fieldKey?: string;
    dataset?: Record<string, string | null | undefined>;
    attributes?: Record<string, SettingsAttributeValue>;
}
interface SectionOptions {
    title: string;
    description?: string;
    trailing?: string;
    className?: string;
    content: string;
}
interface SettingsSubgroupOptions {
    title: string;
    content: string;
    className?: string;
    description?: string;
    trailing?: string;
    tagName?: 'div' | 'section';
    attributes?: Record<string, SettingsAttributeValue>;
}
interface SettingsGroupOptions {
    className?: string;
    attributes?: Record<string, SettingsAttributeValue>;
}
interface SettingsRecordListOptions {
    items: string[];
    empty: string;
    id?: string;
    className?: string;
    attributes?: Record<string, SettingsAttributeValue>;
}
type SettingsStatusBadgeTone = 'active' | 'inactive' | 'warning' | 'danger' | 'neutral';
interface ResetActionOptions {
    titleKey: string;
    messageKey: string;
    descriptionKey?: string;
    confirmTextKey?: string;
    cancelTextKey?: string;
}
interface ApiKey {
    keyId: string;
    label?: string;
    prefix?: string;
    revoked?: boolean;
    expiresAtMs?: number;
    rotationDue?: boolean;
    scopes?: string[];
    createdAtMs?: number;
    lastUsedAtMs?: number;
    requestCount?: number;
    assignedUserId?: number | null;
}
type ApiKeyQuotaMode = 'none' | 'tokens' | 'requests';
interface ApiKeyQuotaLimit {
    limitUnits: number;
}
interface ApiKeyQuotaHourlyLimit {
    limitUnits: number;
    windowHours: number;
}
interface ApiKeyQuotaConfig {
    mode: ApiKeyQuotaMode;
    hourly: ApiKeyQuotaHourlyLimit | null;
    daily: ApiKeyQuotaLimit | null;
    weekly: ApiKeyQuotaLimit | null;
    monthly: ApiKeyQuotaLimit | null;
}
interface ApiKeyQuotaWindowStatus {
    limitUnits: number;
    usedUnits: number;
    reservedUnits: number;
    remainingUnits: number;
    windowStartTsMs: number;
    resetAtMs: number;
    windowMs: number;
}
interface ApiKeyQuotaStatus {
    unit: ApiKeyQuotaMode;
    hourly?: ApiKeyQuotaWindowStatus | null;
    daily?: ApiKeyQuotaWindowStatus | null;
    weekly?: ApiKeyQuotaWindowStatus | null;
    monthly?: ApiKeyQuotaWindowStatus | null;
}
interface ApiKeyQuotaSummary {
    keyId: string;
    config: ApiKeyQuotaConfig;
    status: ApiKeyQuotaStatus;
}
interface WallpaperMetadata {
    type: string | null;
    sizeBytes: number | null;
    width: number | null;
    height: number | null;
}
interface BackupApiEntry {
    backupId: string;
    timestampMs: number | null;
    totalSizeBytes: number | null;
    targetsCompleted: Record<string, boolean>;
    licensingRecoveryState: 'not_applicable' | 'complete' | 'incomplete';
}
interface BackupEntry {
    backupId: string;
    createdAt: number | null;
    sizeBytes: number | null;
    valid: boolean;
    licensingRecoveryState: 'not_applicable' | 'complete' | 'incomplete';
}
type BackupListLoadStatus = 'idle' | 'loading' | 'loaded' | 'failed';
interface BackupOperationState {
    taskId: string;
    type: 'create' | 'restore' | 'verify' | 'delete';
    backupId?: string;
    progress: number;
    message: string;
}
export type { TabDefinition, NormalTabDefinition, AdvancedTabDefinition, SettingsCapabilityStatus, SettingsCapabilityAvailability, PreferenceToggleConfig, ExternalEventConfig, BindControlOptions, ToggleControlOptions, SelectControlOptions, SliderControlOptions, SettingItemOptions, SectionOptions, SettingsSubgroupOptions, SettingsGroupOptions, SettingsRecordListOptions, SettingsStatusBadgeTone, ResetActionOptions, ApiKey, ApiKeyQuotaMode, ApiKeyQuotaLimit, ApiKeyQuotaHourlyLimit, ApiKeyQuotaConfig, ApiKeyQuotaWindowStatus, ApiKeyQuotaStatus, ApiKeyQuotaSummary, WallpaperMetadata, BackupApiEntry, BackupEntry, BackupListLoadStatus, BackupOperationState };
