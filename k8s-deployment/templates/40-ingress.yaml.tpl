apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: __APP__-admin
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  entryPoints: ["websecure"]
  routes:
    - kind: Rule
      match: Host(`__ADMIN_HOST__`) && PathPrefix(`/api`)
      priority: 100
      services:
        - name: __APP__-backend
          port: 8000
    - kind: Rule
      match: Host(`__ADMIN_HOST__`) && PathPrefix(`/`)
      priority: 10
      services:
        - name: __APP__-admin-frontend
          port: 3000
  tls:
    secretName: __TLS_SECRET__
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: __APP__-web
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  entryPoints: ["websecure"]
  routes:
    - kind: Rule
      match: Host(`__WEB_HOST__`) && PathPrefix(`/api`)
      priority: 100
      services:
        - name: __APP__-backend
          port: 8000
    - kind: Rule
      match: Host(`__WEB_HOST__`) && PathPrefix(`/`)
      priority: 10
      services:
        - name: __APP__-web-frontend
          port: 3000
  tls:
    secretName: __TLS_SECRET__
