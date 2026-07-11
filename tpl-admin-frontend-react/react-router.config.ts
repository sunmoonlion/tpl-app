import type { Config } from "@react-router/dev/config";

const configuredBasePath = process.env.BASE_PATH?.trim() || "/";
const basename =
  configuredBasePath === "/"
    ? "/"
    : `/${configuredBasePath.replace(/^\/+|\/+$/g, "")}/`;

export default {
  ssr: false,
  basename,
} satisfies Config;
