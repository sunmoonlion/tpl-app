import { redirect } from "react-router";

import { apiRequest } from "./api";
import { appConfig } from "./config";

export interface AuthUser {
  id: string;
  name: string;
  roles: string[];
}

interface MeResponse {
  user: AuthUser | null;
}

export async function requireUser(): Promise<AuthUser> {
  if (appConfig.authMode === "demo" && import.meta.env.DEV) {
    return { id: "demo-admin", name: "Demo Admin", roles: ["admin"] };
  }

  try {
    const response = await apiRequest<MeResponse>("/api/auth/me");
    if (response.user) return response.user;
  } catch {
    // Authentication failures converge on the product login route.
  }
  throw redirect("/login");
}

export function loginUrl(returnTo = "/"): string {
  const params = new URLSearchParams({ return_to: returnTo });
  return `${appConfig.apiUrl}/api/auth/login?${params.toString()}`;
}

export function logoutUrl(): string {
  return `${appConfig.apiUrl}/api/auth/logout`;
}
