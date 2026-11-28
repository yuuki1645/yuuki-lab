import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import LabPage from "./features/lab/LabPage";
import "./theme.css";
import "./features/lab/lab.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("root missing");
}

/** Same routes as the previous experiment screen: list, then one take. */
createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LabPage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="/lab/:day/:takeId" element={<LabPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
