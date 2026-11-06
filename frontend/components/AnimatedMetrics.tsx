"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";

export function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);
  const previous = useRef(0);
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add({ motion: "(prefers-reduced-motion: no-preference)", reduced: "(prefers-reduced-motion: reduce)" }, (context) => {
      if (context.conditions?.reduced) { setDisplay(value); return; }
      const counter = { value: previous.current };
      gsap.to(counter, { value, duration: 1.1, ease: "power2.out", onUpdate: () => setDisplay(Math.round(counter.value)) });
    });
    previous.current = value;
    return () => media.revert();
  }, [value]);
  return <span aria-label={String(value)}><span aria-hidden="true">{display}</span></span>;
}

export function AnimatedBar({ value }: { value: number }) {
  const bar = useRef<HTMLDivElement>(null);
  const safeValue = Math.min(100, Math.max(0, value));
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.fromTo(bar.current, { scaleX: 0 }, { scaleX: 1, duration: 1, ease: "power3.out" });
    });
    return () => media.revert();
  }, [safeValue]);
  return <div role="progressbar" aria-label="Dimension score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={safeValue} className="h-1.5 w-full bg-[#152449] rounded-full overflow-hidden">
    <div ref={bar} className="h-full origin-left bg-gradient-to-r from-[#FF6A3D] to-[#FF8C38] rounded-full" style={{ width: `${safeValue}%` }} />
  </div>;
}
