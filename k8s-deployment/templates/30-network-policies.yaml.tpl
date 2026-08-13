apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-default-deny
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
  policyTypes: ["Ingress", "Egress"]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-dns-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
  policyTypes: ["Egress"]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - {protocol: UDP, port: 53}
        - {protocol: TCP, port: 53}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-frontend-ingress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchExpressions:
      - key: sunmoonai.com/app
        operator: In
        values: ["__APP__"]
      - key: app.kubernetes.io/component
        operator: In
        values: ["admin-frontend", "web-frontend"]
  policyTypes: ["Ingress"]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: __INGRESS_NAMESPACE__
          podSelector:
            matchLabels:
              __INGRESS_POD_LABEL_KEY__: "__INGRESS_POD_LABEL_VALUE__"
      ports:
        - {protocol: TCP, port: 3000}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-frontend-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchExpressions:
      - key: sunmoonai.com/app
        operator: In
        values: ["__APP__"]
      - key: app.kubernetes.io/component
        operator: In
        values: ["admin-frontend", "web-frontend"]
  policyTypes: ["Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/app: __APP__
              app.kubernetes.io/component: backend-api
      ports:
        - {protocol: TCP, port: 8000}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-backend-ingress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-api
  policyTypes: ["Ingress"]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: __INGRESS_NAMESPACE__
          podSelector:
            matchLabels:
              __INGRESS_POD_LABEL_KEY__: "__INGRESS_POD_LABEL_VALUE__"
        - podSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values: ["admin-frontend", "web-frontend"]
              - key: sunmoonai.com/app
                operator: In
                values: ["__APP__"]
        - podSelector:
            matchLabels:
              sunmoonai.com/allow-__APP__-internal: "true"
      ports:
        - {protocol: TCP, port: 8000}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-backend-api-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-api
  policyTypes: ["Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/backend-dependency: __APP__
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
    - to:
        - namespaceSelector:
            matchLabels:
              sunmoonai.com/data-platform: "true"
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: __CASDOOR_NAMESPACE__
          podSelector:
            matchLabels:
              app: casdoor-sunmoonai
      ports:
        - {protocol: TCP, port: 8000}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-backend-worker-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-worker
  policyTypes: ["Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/backend-dependency: __APP__
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
    - to:
        - namespaceSelector:
            matchLabels:
              sunmoonai.com/data-platform: "true"
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: __CASDOOR_NAMESPACE__
          podSelector:
            matchLabels:
              app: casdoor-sunmoonai
      ports:
        - {protocol: TCP, port: 8000}
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/internal-provider: "true"
      ports:
        - {protocol: TCP, port: 8000}
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - {protocol: TCP, port: 443}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-backend-scheduler-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-scheduler
  policyTypes: ["Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/backend-dependency: __APP__
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
    - to:
        - namespaceSelector:
            matchLabels:
              sunmoonai.com/data-platform: "true"
      ports:
        - {protocol: TCP, port: 5432}
        - {protocol: TCP, port: 6379}
        - {protocol: TCP, port: 5672}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __APP__-backend-migration-egress
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  podSelector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-migration
  policyTypes: ["Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              sunmoonai.com/backend-dependency: __APP__
      ports:
        - {protocol: TCP, port: 5432}
    - to:
        - namespaceSelector:
            matchLabels:
              sunmoonai.com/data-platform: "true"
      ports:
        - {protocol: TCP, port: 5432}
