"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode; label?: string };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[ErrorBoundary${this.props.label ? `:${this.props.label}` : ""}]`, error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="mx-auto flex max-w-lg flex-col items-start gap-4 px-4 py-16">
        <h2 className="text-xl font-semibold">Something went wrong</h2>
        <p className="text-sm text-muted-foreground">
          {this.state.error.message || "An unexpected error occurred."}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            onClick={() => this.setState({ error: null })}
          >
            Retry
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard">Go to Dashboard</Link>
          </Button>
        </div>
      </div>
    );
  }
}
