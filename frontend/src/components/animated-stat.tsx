import { useEffect, useRef } from "react";
import { animate, motion, useInView, useMotionValue, useReducedMotion, useTransform } from "framer-motion";

export function AnimatedStat({ value, suffix }: { value: number; suffix: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reducedMotion = useReducedMotion();
  const count = useMotionValue(0);
  const display = useTransform(count, (current) => Math.round(current).toString());
  useEffect(() => {
    if (!inView) return;
    const animation = animate(count, value, { duration: reducedMotion ? 0 : 1.3, ease: "easeOut" });
    return () => animation.stop();
  }, [inView, value, count, reducedMotion]);
  return <span ref={ref} aria-label={`${value}${suffix}`}><motion.span aria-hidden="true">{display}</motion.span><span aria-hidden="true">{suffix}</span></span>;
}