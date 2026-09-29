import { Montserrat, Anton } from "next/font/google";

// Same two families the backend actually renders with (backend/assets/fonts/
// Montserrat-Variable.ttf, Anton-Regular.ttf) -- loading them here too means
// the Style Gallery's live preview cards use the real font, not a generic
// system-font stand-in, so what you see in the gallery is what renders.
export const montserrat = Montserrat({ subsets: ["latin"], style: ["normal", "italic"], variable: "--font-montserrat", weight: ["400", "700"] });
export const anton = Anton({ subsets: ["latin"], weight: "400", variable: "--font-anton" });

export function fontFamilyForPath(path: string): string {
  if (path.includes("Anton")) return "var(--font-anton)";
  return "var(--font-montserrat)";
}
