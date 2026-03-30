import { Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import HubLayout from "@/app/HubLayout";
import { hubTools } from "@/app/hubTools";

function RouteFallback() {
  return (
    <div className="hub-route-fallback" role="status">
      読み込み中…
    </div>
  );
}

export default function App() {
  const defaultPath = hubTools[0]?.path ?? "/motion";

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<HubLayout />}>
          <Route index element={<Navigate to={defaultPath} replace />} />
          {hubTools.map((t) => (
            <Route
              key={t.id}
              path={t.path}
              element={
                <Suspense fallback={<RouteFallback />}>
                  <t.LazyPage />
                </Suspense>
              }
            />
          ))}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
