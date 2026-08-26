/* SoAI - Shared DOM checkerboard assignment [frontend/assets/ts/core/dom/checkerboardAssignment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type CheckerboardClassName = 'checkerboard-light' | 'checkerboard-dark';

interface CheckerboardClassOptions {
    columns?: number;
    start?: CheckerboardClassName;
}

const CHECKERBOARD_CLASS_PAIR = 'checkerboard-light checkerboard-dark';

const invertCheckerboardClass = (className: CheckerboardClassName): CheckerboardClassName => (className === 'checkerboard-light' ? 'checkerboard-dark' : 'checkerboard-light');

const resolveCheckerboardClass = (index: number, options: CheckerboardClassOptions = {}): CheckerboardClassName => {
    const startClass = options.start ?? 'checkerboard-light';
    const normalizedIndex = Number.isFinite(index) && index > 0 ? Math.trunc(index) : 0;
    const columns = options.columns && Number.isFinite(options.columns) && options.columns > 0 ? Math.trunc(options.columns) : 1;
    const rowIndex = Math.floor(normalizedIndex / columns);
    const columnIndex = normalizedIndex % columns;
    return (rowIndex + columnIndex) % 2 === 0 ? startClass : invertCheckerboardClass(startClass);
};

export { CHECKERBOARD_CLASS_PAIR, invertCheckerboardClass, resolveCheckerboardClass };
export type { CheckerboardClassName, CheckerboardClassOptions };
