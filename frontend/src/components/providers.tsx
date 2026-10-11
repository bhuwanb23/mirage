"use client";

import { Toaster } from "sonner";
import { ErrorBoundary } from "@/components/error-boundary";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      {children}
      <Toaster
        theme="dark"
        position="top-right"
        richColors
        closeButton
        toastOptions={{ duration: 4000 }}
      />
    </ErrorBoundary>
  );
}
