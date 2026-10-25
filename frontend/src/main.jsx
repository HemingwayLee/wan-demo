import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import App from "./App";

const theme = createTheme({
  cssVariables: { colorSchemeSelector: "class" },
  colorSchemes: {
    light: { palette: { primary: { main: "#5b4bd6" }, background: { default: "#f6f6f9" } } },
    dark: { palette: { primary: { main: "#9d8fff" }, background: { default: "#121216", paper: "#1b1b21" } } },
  },
  shape: { borderRadius: 10 },
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider theme={theme} defaultMode="system">
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>
);
