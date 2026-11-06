import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles = {
    default:
      "border-[#FF6A3D]/40 bg-[#FF6A3D]/15 text-[#FF6A3D]",
    secondary:
      "border-[#1E3560] bg-[#152449] text-[#8FA0BE]",
    destructive:
      "border-rose-500/30 bg-rose-500/15 text-rose-300",
    outline: "text-[#F1F5F9] border-[#1E3560] bg-transparent",
    success:
      "border-[#FF6A3D]/50 bg-[#FF6A3D]/25 text-[#FF8C38] font-semibold",
    warning:
      "border-amber-500/30 bg-amber-500/15 text-amber-300",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#FF6A3D] focus:ring-offset-2 focus:ring-offset-[#0A1128]",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
