import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initSessionLifecycle } from "./api";
import App from "./App";
import "./styles.css";

// Antes del primer render: detecta si el navegador se cerró con la sesión
// abierta y, en ese caso, limpia los tokens locales y cierra la sesión en el
// servidor (en segundo plano). Ver src/api.js.
initSessionLifecycle();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
