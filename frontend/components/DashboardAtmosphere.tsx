"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

export function DashboardAtmosphere() {
  const root = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.to(".dashboard-orb", { x: 20, y: -14, duration: 7, repeat: -1, yoyo: true, stagger: 1, ease: "sine.inOut" });
    });
    return () => media.revert();
  }, { scope: root });
  return <div ref={root} className="dashboard-atmosphere" aria-hidden="true"><div className="dashboard-orb dashboard-orb-amber" /><div className="dashboard-orb dashboard-orb-blue" /></div>;
}
