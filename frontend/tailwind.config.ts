import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      colors: {
        border: "#1E3560",
        input: "#1E3560",
        ring: "#FF6A3D",
        background: "#0A1128",
        foreground: "#F1F5F9",
        // Midnight Navy Palette
        midnight: {
          DEFAULT: "#0A1128",
          bg: "#0A1128",
          sidebar: "#0E1B38",
          card: "#101C38",
          cardHover: "#152449",
          border: "#1E3560",
          text: "#F1F5F9",
          muted: "#8FA0BE",
        },
        // Solar Ember Palette
        ember: {
          DEFAULT: "#FF6A3D",
          hover: "#F05526",
          gradientTo: "#FF8C38",
          light: "#FFE5D0",
          glow: "rgba(255, 106, 61, 0.35)",
        },
        // Champagne Pearl Palette
        pearl: {
          DEFAULT: "#FFF5EC",
          light: "#FFF9F5",
          mid: "#FFEADB",
          deep: "#FEDBC4",
          card: "#FBF2EC",
          border: "#EEDFD5",
          text: "#1E293B",
          muted: "#64748B",
        },
        // Backwards compatibility tokens
        obsidian: {
          DEFAULT: "#0A1128",
          bg: "#0A1128",
          card: "#101C38",
          cardHover: "#152449",
          border: "#1E3560",
          text: "#F1F5F9",
          muted: "#8FA0BE",
        },
        amber: {
          DEFAULT: "#FF6A3D",
          hover: "#F05526",
          light: "#FFE5D0",
          muted: "rgba(255, 106, 61, 0.15)",
          glow: "rgba(255, 106, 61, 0.35)",
        },
        mint: {
          DEFAULT: "#FF6A3D",
          hover: "#F05526",
          light: "#FFE5D0",
          muted: "rgba(255, 106, 61, 0.15)",
          glow: "rgba(255, 106, 61, 0.35)",
        },
        primary: {
          DEFAULT: "#FF6A3D",
          foreground: "#FFFFFF",
          50: "#FFF7ED",
          100: "#FFE5D0",
          200: "#FED7AA",
          300: "#FDBA74",
          400: "#FF8C38",
          500: "#FF6A3D",
          600: "#F05526",
          700: "#C2410C",
          800: "#9A3412",
          900: "#0A1128",
        },
        secondary: {
          DEFAULT: "#152449",
          foreground: "#F1F5F9",
        },
        destructive: {
          DEFAULT: "#F87171",
          foreground: "#0A1128",
        },
        muted: {
          DEFAULT: "#152449",
          foreground: "#8FA0BE",
        },
        accent: {
          DEFAULT: "#FF6A3D",
          foreground: "#FFFFFF",
        },
        popover: {
          DEFAULT: "#101C38",
          foreground: "#F1F5F9",
        },
        card: {
          DEFAULT: "#101C38",
          foreground: "#F1F5F9",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

export default config;
