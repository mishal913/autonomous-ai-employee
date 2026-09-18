import {
  StrictMode,
} from "react";

import {
  createRoot,
} from "react-dom/client";

import AuthRoot from "./auth/AuthRoot";

import "./index.css";


createRoot(
  document.getElementById(
    "root"
  )!
).render(

  <StrictMode>
    <AuthRoot />
  </StrictMode>

);
