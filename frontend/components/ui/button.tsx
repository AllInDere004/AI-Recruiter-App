import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  isLoading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "default",
      isLoading = false,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF6A3D] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A1128] disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]";

    const variantStyles = {
      default:
        "bg-gradient-to-r from-[#FF6A3D] to-[#FF8A38] text-white font-bold shadow-md shadow-[#FF6A3D]/30 hover:brightness-110 active:brightness-95",
      destructive:
        "bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30",
      outline:
        "border border-[#1E3560] bg-[#101C38] text-[#F1F5F9] shadow-sm hover:bg-[#152449] hover:text-[#FF6A3D] hover:border-[#FF6A3D]/50",
      secondary:
        "bg-[#152449] text-[#F1F5F9] border border-[#1E3560] shadow-sm hover:bg-[#1E3260]",
      ghost:
        "text-[#8FA0BE] hover:bg-[#152449] hover:text-[#F1F5F9]",
      link: "text-[#FF6A3D] underline-offset-4 hover:underline hover:text-[#FFA066]",
    };

    const sizeStyles = {
      default: "h-10 px-4 py-2",
      sm: "h-8 rounded-md px-3 text-xs",
      lg: "h-12 rounded-xl px-8 text-base",
      icon: "h-10 w-10 p-0",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {isLoading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v8H4z"
            ></path>
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button };
