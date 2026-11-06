import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-lg border border-[#1E3560] bg-[#0A1128] px-3 py-2 text-sm text-[#F1F5F9] placeholder:text-[#8FA0BE]/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF6A3D] focus-visible:border-[#FF6A3D] disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
