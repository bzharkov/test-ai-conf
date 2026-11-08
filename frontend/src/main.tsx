import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Build } from "./pages/Build";
import { Compare } from "./pages/Compare";
import { History } from "./pages/History";
import { Home } from "./pages/Home";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/build/:id" element={<Build />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/history" element={<History />} />
            <Route path="*" element={<p>Страница не найдена</p>} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
