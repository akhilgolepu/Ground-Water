import { z } from "zod";

export const policySchema = z.object({
  pumping: z.number().min(0).max(50),
  recharge: z.number().min(0).max(30),
});
export const defaultPolicy = { pumping: 20, recharge: 10 };

// Illustrative coefficients only; not calibrated to a real aquifer.
export function simulatePolicy(pumping: number, recharge: number) {
  const policy = policySchema.parse({ pumping, recharge });
  return {
    savedVolume: Math.round(policy.pumping * 5200 + policy.recharge * 3200),
    avoidedDrawdown: policy.pumping * 0.12 + policy.recharge * 0.1,
  };
}

export const demoRequestSchema = z.object({
  name: z.string().trim().min(1, "Enter your full name.").max(100),
  organizationType: z.enum(["government", "agriculture", "research", "enterprise"]),
  region: z.string().trim().min(1, "Enter a region or aquifer.").max(200),
  email: z.string().trim().email("Enter a valid work email.").max(255),
});