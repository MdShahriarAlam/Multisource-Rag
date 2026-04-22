/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Segoe UI Variable'", "'Segoe UI'", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'Cascadia Code'", "'Cascadia Mono'", "Consolas", "monospace"],
      },
      colors: {
        base:           "#0f0f0f",
        layer:          "#161616",
        layer2:         "#1d1d1d",
        layer3:         "#252525",
        "fill":         "rgba(255,255,255,0.06)",
        "fill-hover":   "rgba(255,255,255,0.09)",
        "fill-press":   "rgba(255,255,255,0.04)",
        stroke:         "rgba(255,255,255,0.08)",
        "stroke-strong":"rgba(255,255,255,0.14)",
        accent:         "#60cdff",
        "accent-h":     "#0091f8",
        "accent-dark":  "#0067bf",
        "accent-2":     "#a78bfa",
        txt:            "rgba(255,255,255,0.90)",
        muted:          "rgba(255,255,255,0.52)",
        dim:            "rgba(255,255,255,0.30)",
        success:        "#4ade80",
        warning:        "#fbbf24",
        danger:         "#f87171",
      },
      boxShadow: {
        "fluent-sm":   "0 1px 4px rgba(0,0,0,0.45)",
        "fluent":      "0 4px 16px rgba(0,0,0,0.55)",
        "fluent-lg":   "0 8px 32px rgba(0,0,0,0.65)",
        "glow-accent": "0 0 0 3px rgba(96,205,255,0.07)",
        "glow-user":   "0 2px 12px rgba(29,78,216,0.4)",
      },
      keyframes: {
        dot: {
          "0%,80%,100%": { transform: "scale(0.45)", opacity: "0.25" },
          "40%":          { transform: "scale(1.1)",  opacity: "1"   },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to:   { opacity: "1", transform: "translateY(0)"   },
        },
        reveal: {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        float: {
          "0%,100%": { transform: "translateY(0px)"   },
          "50%":     { transform: "translateY(-3px)"  },
        },
      },
      animation: {
        dot:     "dot 1.6s infinite ease-in-out",
        slideUp: "slideUp 0.2s cubic-bezier(0,0,0.2,1)",
        reveal:  "reveal 0.15s ease-out",
        float:   "float 3s ease-in-out infinite",
      },
      borderRadius: {
        fluent:      "4px",
        "fluent-md": "8px",
        "fluent-lg": "12px",
        "fluent-xl": "16px",
      },
    },
  },
  plugins: [],
};
