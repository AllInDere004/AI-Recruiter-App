"use client";

import { useRef, type ReactNode } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

/** Owns homepage motion while the page content stays server-rendered. */
export function HomepageMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const scope = root.current;
    if (!scope) return;
    const select = gsap.utils.selector(scope);
    const media = gsap.matchMedia();

    media.add({
      motion: "(prefers-reduced-motion: no-preference)",
      desktop: "(min-width: 768px)",
      hover: "(hover: hover) and (pointer: fine)",
    }, (context) => {
      if (!context.conditions?.motion) return;
      const desktop = context.conditions.desktop;
      const distance = desktop ? 24 : 14;
      const entrance = { duration: 0.7, ease: "power3.out", clearProps: "transform,opacity" };
      const intro = gsap.timeline();
      intro.from(select("[data-home-nav]"), { ...entrance, y: -14, opacity: 0 })
        .from(select("[data-home-badge]"), { ...entrance, y: 10, opacity: 0 }, 0.12)
        .from(select("[data-home-heading]"), { ...entrance, y: distance }, 0.2)
        // Inline words keep the original wrapping and gradient; only opacity changes.
        .from(select("[data-home-word]"), { opacity: 0, stagger: 0.035, duration: 0.45, clearProps: "opacity" }, 0.2)
        .from(select("[data-home-description]"), { ...entrance, y: distance, opacity: 0 }, 0.4)
        .from(select("[data-home-actions], [data-home-trust]"), { ...entrance, y: 12, opacity: 0, stagger: 0.08 }, 0.5);

      select("[data-home-preview], [data-home-feature-heading]").forEach((element: HTMLElement) => {
        gsap.from(element, { ...entrance, y: distance, opacity: 0,
          scrollTrigger: { trigger: element, start: "top 92%", once: true },
        });
      });
      const cards = select("[data-home-feature]");
      if (desktop) {
        gsap.from(cards, { ...entrance, y: distance, opacity: 0, stagger: 0.12,
          scrollTrigger: { trigger: cards[0], start: "top 90%", once: true },
        });
      } else {
        // Separate triggers keep lower cards visible only when they enter on mobile.
        cards.forEach((element: HTMLElement) => gsap.from(element, {
          ...entrance, y: distance, opacity: 0,
          scrollTrigger: { trigger: element, start: "top 94%", once: true },
        }));
      }

      const floating = gsap.to(select("[data-float]"), {
        y: desktop ? -6 : -3, duration: 3.5, stagger: 0.3, repeat: -1, yoyo: true, ease: "sine.inOut",
      });
      const glow = gsap.to(select("[data-home-glow]"), {
        x: desktop ? 16 : 6, y: desktop ? -10 : -4, duration: 6, repeat: -1, yoyo: true, ease: "sine.inOut",
      });
      const loops = [floating, glow];
      // Stop perpetual work outside the hero or while the browser tab is hidden.
      let visible = true;
      const syncLoops = () => loops.forEach((tween) => tween.paused(!visible || document.hidden));
      const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; syncLoops(); });
      const hero = scope.querySelector("[data-hero-copy]");
      if (hero) observer.observe(hero);
      document.addEventListener("visibilitychange", syncLoops);
      syncLoops();

      const listeners: Array<() => void> = [];
      if (context.conditions.hover) {
        select("[data-home-cta]").forEach((button: HTMLElement) => {
          // Reuse one tween per button so rapid pointer movement cannot pile up tweens.
          const hover = gsap.to(button, {
            scale: 1.025, boxShadow: "0 6px 26px rgba(255,106,61,0.48)",
            duration: 0.24, ease: "power2.out", paused: true,
          });
          let pointerInside = false;
          let focused = false;
          const sync = () => { if (pointerInside || focused) hover.play(); else hover.reverse(); };
          const enter = () => { pointerInside = true; sync(); };
          const leave = () => { pointerInside = false; sync(); };
          const focus = () => { focused = true; sync(); };
          const blur = () => { focused = false; sync(); };
          button.addEventListener("pointerenter", enter);
          button.addEventListener("pointerleave", leave);
          button.addEventListener("focus", focus);
          button.addEventListener("blur", blur);
          listeners.push(() => {
            button.removeEventListener("pointerenter", enter);
            button.removeEventListener("pointerleave", leave);
            button.removeEventListener("focus", focus);
            button.removeEventListener("blur", blur);
          });
        });
      }
      let active = true;
      document.fonts.ready.then(() => { if (active) ScrollTrigger.refresh(); });
      return () => {
        active = false;
        observer.disconnect();
        document.removeEventListener("visibilitychange", syncLoops);
        listeners.forEach((remove) => remove());
      };
    }, scope);
    return () => media.revert();
  }, { scope: root });

  return <div ref={root} className="contents" data-home-motion>{children}</div>;
}
