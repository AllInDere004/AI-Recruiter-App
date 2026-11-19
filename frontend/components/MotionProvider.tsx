"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/** Scoped route motion; content remains readable before JavaScript loads. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const progress = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    // The homepage owns its animations through HomepageMotion/useGSAP.
    if (pathname === "/") return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const scope = root.current;
      if (!scope) return;
      const context = gsap.context(() => {
        const heading = scope.querySelector("h1, h2");
        if (heading) gsap.from(heading, { y: 22, opacity: 0, duration: 0.7, ease: "power3.out", clearProps: "transform,opacity" });
        gsap.from(scope.querySelectorAll("aside nav > a"), {
          x: -16, opacity: 0, stagger: 0.055, duration: 0.45, clearProps: "transform,opacity",
        });
        const targets = scope.querySelectorAll<HTMLElement>("[data-reveal], [data-motion-card], main > .pearl-hero");
        targets.forEach((target, index) => {
          gsap.from(target, {
            y: 26, opacity: 0, duration: 0.65, delay: (index % 4) * 0.06,
            ease: "power3.out", clearProps: "transform,opacity",
            scrollTrigger: { trigger: target, start: "top 94%", once: true },
          });
        });
        gsap.from(scope.querySelectorAll("[data-hero-copy] > :not(h1)"), {
          y: 20, opacity: 0, stagger: 0.09, duration: 0.7, delay: 0.1,
          ease: "power3.out", clearProps: "transform,opacity",
        });
        scope.querySelectorAll<HTMLElement>("[data-float]").forEach((target, index) => {
          gsap.to(target, { y: index % 2 ? 8 : -8, duration: 2.8 + index * 0.4, repeat: -1, yoyo: true, ease: "sine.inOut" });
        });
        if (progress.current) gsap.fromTo(progress.current, { scaleX: 0 }, {
          scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.2 },
        });
      }, scope);
      const onOver = (event: PointerEvent) => {
        if (event.pointerType === "touch") return;
        const button = (event.target as Element).closest<HTMLElement>("button:not(:disabled), [data-motion-link]");
        if (!button || button.contains(event.relatedTarget as Node | null)) return;
        context.add(() => { gsap.to(button, { scale: 1.025, duration: 0.22, overwrite: "auto" }); });
      };
      const onOut = (event: PointerEvent) => {
        const button = (event.target as Element).closest<HTMLElement>("button, [data-motion-link]");
        if (!button || button.contains(event.relatedTarget as Node | null)) return;
        context.add(() => { gsap.to(button, { scale: 1, duration: 0.25, overwrite: "auto", clearProps: "transform" }); });
      };
      scope.addEventListener("pointerover", onOver);
      scope.addEventListener("pointerout", onOut);
      // Refresh after fonts settle, without retaining callbacks across routes.
      let active = true;
      document.fonts.ready.then(() => { if (active) ScrollTrigger.refresh(); });
      return () => {
        active = false;
        scope.removeEventListener("pointerover", onOver);
        scope.removeEventListener("pointerout", onOut);
        context.revert();
      };
    });
    return () => media.revert();
  }, [pathname]);

  return <div ref={root} className="motion-root">
    <div ref={progress} className="reading-progress" aria-hidden="true" />
    {children}
  </div>;
}


