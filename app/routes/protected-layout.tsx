import { AppShell } from "~/components/app-shell";
import { RouteErrorBoundary } from "~/components/route-error-boundary";
import { requireUser } from "~/lib/auth";

import type { Route } from "./+types/protected-layout";

export async function clientLoader() {
  return { user: await requireUser() };
}

export default function ProtectedLayout({ loaderData }: Route.ComponentProps) {
  return <AppShell user={loaderData.user} />;
}

export function ErrorBoundary() {
  return <RouteErrorBoundary />;
}
