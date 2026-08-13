apiVersion: v1
kind: Namespace
metadata:
  name: __NAMESPACE__
  labels:
    app.kubernetes.io/part-of: sunmoonai-app-platform
    sunmoonai.com/platform: "true"
    sunmoonai.com/managed-by: architecture-v2
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-backend-api
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-backend-worker
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-backend-scheduler
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-backend-migration
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-admin-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __APP__-web-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
automountServiceAccountToken: false
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: __APP__-backend-config
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
data:
  ENV: production
  LOG_LEVEL: INFO
  SERVICE_NAME: __APP__-backend
  DEPLOYMENT_ID: __RELEASE_ID__
  APP_SLUG: __APP__
  REDIS_HOST: __REDIS_HOST__
  REDIS_PORT: "__REDIS_PORT__"
  REDIS_DB: "__REDIS_DB__"
  CASDOOR_ENDPOINT: __CASDOOR_ORIGIN__
  CASDOOR_DISCOVERY_URL: __CASDOOR_ORIGIN__/.well-known/openid-configuration
  CASDOOR_BACKCHANNEL_ENDPOINT: __CASDOOR_BACKCHANNEL_ORIGIN__
  CASDOOR_ORGANIZATION: __CASDOOR_ORGANIZATION__
  CASDOOR_VERIFY_SSL: "true"
  ADMIN_CASDOOR_CLIENT_ID: __ADMIN_CLIENT_ID__
  ADMIN_CASDOOR_REDIRECT_URI: __ADMIN_ORIGIN__/api/auth/admin/callback
  ADMIN_CASDOOR_APPLICATION: __ADMIN_APPLICATION__
  ADMIN_AUTH_POLICY_VERSION: __APP__-admin-v2
  ADMIN_AUTH_ROLE_ALLOWLIST: admin,operator
  ADMIN_AUTH_SCOPE_ALLOWLIST: __APP__:admin
  ADMIN_FRONTEND_BASE_URL: __ADMIN_ORIGIN__
  ADMIN_FRONTEND_ALLOWED_ORIGINS: __ADMIN_ORIGIN__
  ADMIN_AUTH_DEFAULT_RETURN_TO: /
  ADMIN_AUTH_ALLOWED_RETURN_PATHS: /
  WEB_CASDOOR_CLIENT_ID: __WEB_CLIENT_ID__
  WEB_CASDOOR_REDIRECT_URI: __WEB_ORIGIN__/api/auth/web/callback
  WEB_CASDOOR_APPLICATION: __WEB_APPLICATION__
  WEB_AUTH_POLICY_VERSION: __APP__-web-v2
  WEB_AUTH_ROLE_ALLOWLIST: member
  WEB_AUTH_SCOPE_ALLOWLIST: profile:read
  WEB_FRONTEND_BASE_URL: __WEB_ORIGIN__
  WEB_FRONTEND_ALLOWED_ORIGINS: __WEB_ORIGIN__
  WEB_AUTH_DEFAULT_RETURN_TO: /zh-CN/dashboard
  WEB_AUTH_ALLOWED_RETURN_PATHS: /zh-CN/dashboard,/en/dashboard,/zh-CN/login,/en/login
  WEB_FRONTEND_DEFAULT_LOCALE: zh-CN
  SESSION_COOKIE_SECURE: "true"
  ALLOWED_HOSTS: __APP__-backend,__APP__-backend.__NAMESPACE__,__APP__-backend.__NAMESPACE__.svc,__APP__-backend.__NAMESPACE__.svc.cluster.local,__ADMIN_HOST__,__WEB_HOST__
  REFERENCE_INTERACTION_ENABLED: "false"
  SERVICE_AUTH_SUBJECT_BINDINGS_JSON: "{}"
  CELERY_QUEUE: __APP__.default
  # Never inherit Celery's CPU-count prefork default inside a memory-limited
  # container. Increase this only together with worker memory/load evidence;
  # horizontal scaling remains the primary Kubernetes capacity mechanism.
  CELERY_WORKER_CONCURRENCY: "2"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: __APP__-admin-frontend-config
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
data:
  DEPLOYMENT_ENV: production
  AUTH_APP: __APP__
  APP_ORIGIN: __ADMIN_ORIGIN__
  BACKEND_INTERNAL_URL: http://__APP__-backend:8000
  DEPLOYMENT_ID: __RELEASE_ID__-admin
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: __APP__-web-frontend-config
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
data:
  DEPLOYMENT_ENV: production
  AUTH_APP: __APP__
  APP_ORIGIN: __WEB_ORIGIN__
  BACKEND_INTERNAL_URL: http://__APP__-backend:8000
  DEPLOYMENT_ID: __RELEASE_ID__-web
  REFERENCE_UI_ENABLED: "false"
---
apiVersion: v1
kind: Service
metadata:
  name: __APP__-backend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
spec:
  selector:
    sunmoonai.com/app: __APP__
    app.kubernetes.io/component: backend-api
  ports:
    - name: http
      port: 8000
      targetPort: http
---
apiVersion: v1
kind: Service
metadata:
  name: __APP__-admin-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
spec:
  selector:
    sunmoonai.com/app: __APP__
    app.kubernetes.io/component: admin-frontend
  ports:
    - name: http
      port: 3000
      targetPort: http
---
apiVersion: v1
kind: Service
metadata:
  name: __APP__-web-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
spec:
  selector:
    sunmoonai.com/app: __APP__
    app.kubernetes.io/component: web-frontend
  ports:
    - name: http
      port: 3000
      targetPort: http
