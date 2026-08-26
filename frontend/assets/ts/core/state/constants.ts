/* SoAI - Shared state constants [frontend/assets/ts/core/state/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type StatusColor = 'grey' | 'orange' | 'green' | 'blue' | 'red' | 'darkgreen' | 'persistentgreen';

interface StatusDefinition {
    color: StatusColor;
    description: string;
    group?: string;
}

type StatusDefinitions = Record<string, StatusDefinition>;

interface StatusTags {
    active: readonly string[];
    error: readonly string[];
    transition: readonly string[];
}

interface StatusConfig {
    defaultStatus: string;
    definitions: StatusDefinitions;
    allowedColors: readonly StatusColor[];
    tags: StatusTags;
}

const DEFAULT_STATUS_ALLOWED_COLORS: readonly StatusColor[] = Object.freeze(['grey', 'orange', 'green', 'blue', 'red', 'darkgreen', 'persistentgreen']);

const DEFAULT_STATUS_DEFINITIONS: StatusDefinitions = Object.freeze({
    UNKNOWN: { color: 'grey', description: '' },
    STOPPED: { color: 'grey', description: '' },
    STARTING: { color: 'blue', description: '' },
    LOADING: { color: 'blue', description: '' },
    IDLE: { color: 'green', description: '' },
    READY_PENDING_DISPATCH: { color: 'blue', description: '' },
    READY: { color: 'green', description: '' },
    READY_DIRTY: { color: 'green', description: '' },
    PROCESSING: { color: 'orange', description: '' },
    STOPPING: { color: 'blue', description: '' },
    ERROR: { color: 'red', description: '' },
    QUARANTINED: { color: 'red', description: '' },
    DISABLED: { color: 'grey', description: '' },
    INCOMPATIBLE: { color: 'red', description: '' },
    NOT_DETECTED: { color: 'grey', description: '' },
    BACKEND_NOT_INSTALLED: { color: 'grey', description: '' },
    BACKEND_INSTALLING: { color: 'orange', description: '' },
    BACKEND_UPDATING: { color: 'blue', description: '' },
    REMOVING_BACKEND: { color: 'blue', description: '' },
    DELETING: { color: 'blue', description: '' },
    INSTALL_ERROR: { color: 'red', description: '' },
    LOAD_ERROR: { color: 'red', description: '' },
    UPDATE_ERROR: { color: 'red', description: '' },
    BACKEND_UNINSTALL_ERROR: { color: 'red', description: '' },
    DELETE_ERROR: { color: 'red', description: '' },
    PERSISTENT_READY: { color: 'persistentgreen', description: '' },
    ABSENT: { color: 'grey', description: '' }
});

const DEFAULT_STATUS_TAGS: StatusTags = Object.freeze({
    active: Object.freeze(['IDLE', 'READY', 'READY_DIRTY', 'PROCESSING', 'PERSISTENT_READY']),
    error: Object.freeze(['ERROR', 'QUARANTINED', 'INSTALL_ERROR', 'LOAD_ERROR', 'UPDATE_ERROR', 'BACKEND_UNINSTALL_ERROR', 'DELETE_ERROR', 'INCOMPATIBLE']),
    transition: Object.freeze(['STARTING', 'LOADING', 'READY_PENDING_DISPATCH', 'STOPPING', 'BACKEND_INSTALLING', 'BACKEND_UPDATING', 'REMOVING_BACKEND', 'DELETING'])
});

const DEFAULT_STATUS_CONFIG: StatusConfig = Object.freeze({
    defaultStatus: 'UNKNOWN',
    definitions: DEFAULT_STATUS_DEFINITIONS,
    allowedColors: DEFAULT_STATUS_ALLOWED_COLORS,
    tags: DEFAULT_STATUS_TAGS
});

const MAIN_STATE_DEFINITIONS: StatusDefinitions = Object.freeze({
    STARTING: { color: 'blue', description: '' },
    READY: { color: 'green', description: '' },
    ACTIVE: { color: 'orange', description: '' },
    ERROR: { color: 'red', description: '' },
    RECONNECTING: { color: 'red', description: '' },
    STOPPING: { color: 'blue', description: '' },
    UNKNOWN: { color: 'grey', description: '' }
});

const COLLECTION_STATUS_CLASS_MAP: Record<string, string> = Object.freeze({
    green: 'status-success',
    darkgreen: 'status-success',
    persistentgreen: 'status-persistent',
    orange: 'status-warning',
    blue: 'status-info',
    red: 'status-error'
});

const COLLECTION_BADGE_CLASS_MAP: Record<string, string> = Object.freeze({
    green: 'status-green',
    darkgreen: 'status-darkgreen',
    persistentgreen: 'status-persistentgreen',
    orange: 'status-orange',
    blue: 'status-blue',
    red: 'status-red'
});

export { COLLECTION_BADGE_CLASS_MAP, COLLECTION_STATUS_CLASS_MAP, DEFAULT_STATUS_ALLOWED_COLORS, DEFAULT_STATUS_CONFIG, DEFAULT_STATUS_DEFINITIONS, DEFAULT_STATUS_TAGS, MAIN_STATE_DEFINITIONS };

export type { StatusColor, StatusDefinition, StatusDefinitions, StatusTags, StatusConfig };
