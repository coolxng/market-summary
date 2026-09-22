export type Theme = "paper" | "ink";

export const THEME_STORAGE_KEY = "daily-tape-theme";

export const THEME_COLORS: Record<Theme, string> = {
  paper: "#f3f0e7",
  ink: "#080808",
};
