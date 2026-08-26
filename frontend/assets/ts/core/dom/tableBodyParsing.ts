/* SoAI - Shared DOM table body parsing [frontend/assets/ts/core/dom/tableBodyParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const parseTableBodyElement = (inputArguments: { documentRef: Document; html: string }): HTMLTableSectionElement => {
    const { documentRef, html } = inputArguments;
    const table = documentRef.createElement('table');
    const tableBody = documentRef.createElement('tbody');
    table.appendChild(tableBody);
    const range = documentRef.createRange();
    range.selectNodeContents(tableBody);
    tableBody.appendChild(range.createContextualFragment(html));
    return tableBody;
};

export { parseTableBodyElement };
