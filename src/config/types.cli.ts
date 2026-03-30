export type CliBannerTaglineMode = "random" | "default" | "off";

export type CliConfig = {
  /** Locale for CLI output (e.g., "en", "fr"). Detected from environment if omitted. */
  locale?: string;
  banner?: {
    /**
     * Controls CLI banner tagline behavior.
     * - "random": pick from tagline pool (default)
     * - "default": always use DEFAULT_TAGLINE
     * - "off": hide tagline text
     */
    taglineMode?: CliBannerTaglineMode;
  };
};
