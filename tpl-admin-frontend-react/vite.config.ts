import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

const configuredBasePath = process.env.BASE_PATH?.trim() || "/";
const basename =
  configuredBasePath === "/"
    ? "/"
    : `/${configuredBasePath.replace(/^\/+|\/+$/g, "")}`;

export default defineConfig({
  base: basename === "/" ? "/" : `${basename}/`,
  plugins: [reactRouter(), tsconfigPaths()],
  server: { host: true },
  preview: { host: true },
});
