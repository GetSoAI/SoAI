/* SoAI - Charts feature density [frontend/assets/ts/features/charts/datatransforms/density.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DataPoint, DensityMode } from '@features/charts/datatransforms/types.ts';

type BucketPointSet = {
    first: DataPoint;
    last: DataPoint;
    min: DataPoint;
    max: DataPoint;
    sum: number;
    count: number;
};

const createAveragePoint = (bucket: BucketPointSet): DataPoint => ({
    ...bucket.last,
    timestamp: bucket.last.timestamp,
    value: bucket.sum / bucket.count
});

const appendUniquePoint = (target: DataPoint[], point: DataPoint): void => {
    const previous = target[target.length - 1];
    if (!previous || previous.timestamp !== point.timestamp) {
        target.push(point);
    }
};

const appendShapeBucket = (target: DataPoint[], bucket: BucketPointSet): void => {
    appendUniquePoint(target, bucket.first);
    const minFirst = bucket.min.timestamp <= bucket.max.timestamp;
    appendUniquePoint(target, minFirst ? bucket.min : bucket.max);
    appendUniquePoint(target, minFirst ? bucket.max : bucket.min);
    appendUniquePoint(target, bucket.last);
};

const reduceSmallTarget = (points: DataPoint[], target: number): DataPoint[] => {
    const first = points[0];
    const last = points[points.length - 1];
    if (!first || !last) {
        return [];
    }
    if (target === 1) {
        return [last];
    }
    if (target === 2) {
        return first.timestamp === last.timestamp ? [last] : [first, last];
    }
    let minPoint = first;
    let maxPoint = first;
    for (const point of points) {
        if (point.value < minPoint.value) {
            minPoint = point;
        }
        if (point.value > maxPoint.value) {
            maxPoint = point;
        }
    }
    const middle = minPoint.timestamp <= maxPoint.timestamp ? minPoint : maxPoint;
    const reduced: DataPoint[] = [];
    appendUniquePoint(reduced, first);
    appendUniquePoint(reduced, middle);
    appendUniquePoint(reduced, last);
    return reduced.slice(-target);
};

const reduceSeriesDensity = (points: DataPoint[], limit: number, mode: DensityMode = 'shape'): DataPoint[] => {
    const target = Math.max(1, Number.isFinite(limit) ? Math.floor(limit) : points.length);
    if (points.length <= target) {
        return points;
    }
    if (target < 4) {
        return reduceSmallTarget(points, target);
    }
    const bucketCount = Math.max(1, Math.floor(mode === 'average' ? target : target / 4));
    const bucketSize = points.length / bucketCount;
    const reduced: DataPoint[] = [];

    for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
        const start = Math.floor(bucketIndex * bucketSize);
        const end = Math.min(points.length, Math.floor((bucketIndex + 1) * bucketSize));
        const first = points[start];
        if (!first) {
            continue;
        }
        let bucket: BucketPointSet = { first, last: first, min: first, max: first, sum: first.value, count: 1 };
        for (let pointIndex = start + 1; pointIndex < end; pointIndex += 1) {
            const point = points[pointIndex];
            if (!point) {
                continue;
            }
            bucket = {
                ...bucket,
                last: point,
                min: point.value < bucket.min.value ? point : bucket.min,
                max: point.value > bucket.max.value ? point : bucket.max,
                sum: bucket.sum + point.value,
                count: bucket.count + 1
            };
        }
        if (mode === 'average') {
            appendUniquePoint(reduced, createAveragePoint(bucket));
        } else {
            appendShapeBucket(reduced, bucket);
        }
    }

    const last = points[points.length - 1];
    if (last) {
        appendUniquePoint(reduced, last);
    }
    return reduced.length > target ? reduceSeriesDensity(reduced, target, mode) : reduced;
};

export { reduceSeriesDensity };
