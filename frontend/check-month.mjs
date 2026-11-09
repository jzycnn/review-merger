import assert from 'node:assert/strict';
import {previousReviewMonth} from './src/reviewMonth.ts';
assert.equal(previousReviewMonth(new Date(2026,10,6)),'2026-10');
assert.equal(previousReviewMonth(new Date(2026,0,5)),'2025-12');
assert.equal(previousReviewMonth(new Date(2026,2,31)),'2026-02');
console.log('默认上月：3项边界检查通过');
