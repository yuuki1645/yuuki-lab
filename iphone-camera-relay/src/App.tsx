import { Route, Routes } from "react-router-dom";
import CameraPage from "./pages/CameraPage";
import HomePage from "./pages/HomePage";
import MonitorPage from "./pages/MonitorPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/camera" element={<CameraPage />} />
      <Route path="/monitor" element={<MonitorPage />} />
    </Routes>
  );
}
