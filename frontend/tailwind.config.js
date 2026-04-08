/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-body)", "Poppins", "ui-sans-serif", "system-ui"],
        heading: ["var(--font-heading)", "Roboto", "ui-sans-serif", "system-ui"]
      },
      colors: {
        bg: {
          primary: "#100944",
          secondary: "#140c4f"
        },
        accent: {
          primary: "#6C63FF",
          secondary: "#8BE9FD"
        },
        text: {
          primary: "#FFFFFF",
          secondary: "#B8B8D1"
        }
      },
      borderRadius: {
        xl: "16px"
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,255,255,0.06), 0 12px 40px rgba(108,99,255,0.25), 0 0 50px rgba(139,233,253,0.10)",
        card: "0 0 0 1px rgba(255,255,255,0.06), 0 18px 50px rgba(0,0,0,0.35)"
      },
      keyframes: {
        floaty: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" }
        },
        shimmer: {
          "0%": { transform: "translateX(-35%)" },
          "100%": { transform: "translateX(35%)" }
        }
      },
      animation: {
        floaty: "floaty 6s ease-in-out infinite",
        shimmer: "shimmer 2.2s ease-in-out infinite"
      }
    }
  },
  plugins: []
};

