import {
  index,
  layout,
  route,
  type RouteConfig,
} from "@react-router/dev/routes";

export default [
  route("login", "./routes/login.tsx"),
  layout("./routes/protected-layout.tsx", [
    index("./routes/home.tsx"),
    route("reference", "./routes/reference.tsx"),
    route("forbidden", "./routes/forbidden.tsx"),
  ]),
  route("*", "./routes/not-found.tsx"),
] satisfies RouteConfig;
