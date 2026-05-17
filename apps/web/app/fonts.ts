import { Antonio, Geist, IBM_Plex_Mono, Instrument_Serif } from "next/font/google";

export const fontAntonio = Antonio({
  subsets: ["latin"],
  variable: "--font-antonio",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const fontInstrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  variable: "--font-instrument-serif",
  display: "swap",
  weight: ["400"],
  style: ["normal", "italic"],
});

export const fontGeist = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

export const fontIbmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
  weight: ["400", "500"],
});

export const fontVariables = [
  fontAntonio.variable,
  fontInstrumentSerif.variable,
  fontGeist.variable,
  fontIbmPlexMono.variable,
].join(" ");
