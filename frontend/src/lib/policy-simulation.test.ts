import { describe, test } from "node:test";
import { strict as assert } from "node:assert";
const expect = (actual: unknown) => ({ toBe: (expected: unknown) => assert.equal(actual, expected), toEqual: (expected: unknown) => assert.deepEqual(actual, expected) });
import { defaultPolicy, policySchema, simulatePolicy, demoRequestSchema } from "./policy-simulation";

describe("policy controls", () => {
  test("pumping defaults to 20 and is bounded from 0 to 50", () => {
    expect(defaultPolicy.pumping).toBe(20);
    expect(policySchema.safeParse({ pumping: 0, recharge: 10 }).success).toBe(true);
    expect(policySchema.safeParse({ pumping: 50, recharge: 10 }).success).toBe(true);
    expect(policySchema.safeParse({ pumping: 51, recharge: 10 }).success).toBe(false);
    expect(policySchema.safeParse({ pumping: -1, recharge: 10 }).success).toBe(false);
  });
  test("MAR defaults to 10 and is bounded from 0 to 30", () => {
    expect(defaultPolicy.recharge).toBe(10);
    expect(policySchema.safeParse({ pumping: 20, recharge: 0 }).success).toBe(true);
    expect(policySchema.safeParse({ pumping: 20, recharge: 30 }).success).toBe(true);
    expect(policySchema.safeParse({ pumping: 20, recharge: 31 }).success).toBe(false);
    expect(policySchema.safeParse({ pumping: 20, recharge: -1 }).success).toBe(false);
  });
  test("illustrative volume and mitigation respond to both controls", () => {
    expect(simulatePolicy(20, 10).savedVolume).toBe(136000);
    expect(simulatePolicy(0, 0)).toEqual({ savedVolume: 0, avoidedDrawdown: 0 });
    expect(simulatePolicy(50, 30)).toEqual({ savedVolume: 356000, avoidedDrawdown: 9 });
  });
  test("only the four requested organization types are accepted", () => {
    const input = { name: "Sample User", region: "Sample Basin", email: "sample@example.org" };
    for (const organizationType of ["government", "agriculture", "research", "enterprise"]) {
      expect(demoRequestSchema.safeParse({ ...input, organizationType }).success).toBe(true);
    }
    expect(demoRequestSchema.safeParse({ ...input, organizationType: "ngo" }).success).toBe(false);
  });
});