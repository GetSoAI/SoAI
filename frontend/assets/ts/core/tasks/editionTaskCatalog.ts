/* SoAI - Product-neutral frontend task catalog contribution [frontend/assets/ts/core/tasks/editionTaskCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface EditionTaskCatalog {
    readonly taskTypeMappings: Readonly<Record<string, string>>;
    readonly operationLabels: Readonly<Record<string, () => string>>;
    readonly backgroundActivityOperationTypes: readonly string[];
}

const EMPTY_EDITION_TASK_CATALOG: EditionTaskCatalog = Object.freeze({
    taskTypeMappings: Object.freeze({}),
    operationLabels: Object.freeze({}),
    backgroundActivityOperationTypes: Object.freeze([])
});

let selectedCatalog: EditionTaskCatalog = EMPTY_EDITION_TASK_CATALOG;
let catalogConfigured = false;

const configureEditionTaskCatalog = (catalog: EditionTaskCatalog): void => {
    if (catalogConfigured) {
        throw new Error('Frontend edition task catalog is already configured');
    }
    selectedCatalog = Object.freeze({
        taskTypeMappings: Object.freeze({ ...catalog.taskTypeMappings }),
        operationLabels: Object.freeze({ ...catalog.operationLabels }),
        backgroundActivityOperationTypes: Object.freeze([...catalog.backgroundActivityOperationTypes])
    });
    catalogConfigured = true;
};

const resolveEditionTaskOperationType = (taskType: string): string | null => {
    return selectedCatalog.taskTypeMappings[taskType] ?? null;
};

const resolveEditionTaskOperationLabel = (operationType: string): string | null => {
    const getLabel = selectedCatalog.operationLabels[operationType];
    return getLabel ? getLabel() : null;
};

const resolveEditionBackgroundActivityOperationTypes = (): readonly string[] => selectedCatalog.backgroundActivityOperationTypes;

export { configureEditionTaskCatalog, resolveEditionBackgroundActivityOperationTypes, resolveEditionTaskOperationLabel, resolveEditionTaskOperationType };
export type { EditionTaskCatalog };
