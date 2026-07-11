import { AppShell } from "~/components/app-shell";
import { requireUser } from "~/lib/auth";

import type { Route } from "./+types/protected-layout";

export async function clientLoader() {
  return { user: await requireUser() };
}

export default function ProtectedLayout({ loaderData }: Route.ComponentProps) {
  return <AppShell user={loaderData.user} />;
}
