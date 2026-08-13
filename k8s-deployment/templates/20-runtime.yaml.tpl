apiVersion: apps/v1
kind: Deployment
metadata:
  name: __APP__-backend-api
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-backend
    app.kubernetes.io/component: backend-api
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  replicas: __API_REPLICAS__
  revisionHistoryLimit: 3
  minReadySeconds: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-backend
        app.kubernetes.io/component: backend-api
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: app-platform-v2
        sunmoonai.com/internal-provider: "true"
      annotations:
        sunmoonai.com/release-id: __RELEASE_ID__
    spec:
      serviceAccountName: __APP__-backend-api
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 45
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              sunmoonai.com/app: __APP__
              app.kubernetes.io/component: backend-api
      containers:
        - name: api
          image: __BACKEND_IMAGE__
          imagePullPolicy: IfNotPresent
          command: ["uvicorn"]
          args: ["app.bootstrap.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
          ports:
            - name: http
              containerPort: 8000
          envFrom:
            - configMapRef:
                name: __APP__-backend-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: API_DATABASE_URL
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: REDIS_PASSWORD
            - name: ADMIN_CASDOOR_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: ADMIN_CASDOOR_CLIENT_SECRET
            - name: WEB_CASDOOR_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: WEB_CASDOOR_CLIENT_SECRET
            - name: CELERY_BROKER_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: API_CELERY_BROKER_URL
          startupProbe:
            httpGet:
              path: /health/live
              port: http
              httpHeaders:
                - name: Host
                  value: __APP__-backend
            periodSeconds: 2
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
              httpHeaders:
                - name: Host
                  value: __APP__-backend
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health/live
              port: http
              httpHeaders:
                - name: Host
                  value: __APP__-backend
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-ec", "sleep 10"]
          resources:
            requests:
              cpu: 100m
              memory: 192Mi
            limits:
              cpu: "1"
              memory: 768Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 128Mi
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: __APP__-backend-api
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-api
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: __APP__-backend-api
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: __APP__-backend-api
  minReplicas: __API_REPLICAS__
  maxReplicas: 6
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
    scaleUp:
      stabilizationWindowSeconds: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __APP__-backend-worker
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-backend
    app.kubernetes.io/component: backend-worker
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  replicas: __WORKER_REPLICAS__
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-worker
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-backend
        app.kubernetes.io/component: backend-worker
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: app-platform-v2
    spec:
      serviceAccountName: __APP__-backend-worker
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 90
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: worker
          image: __BACKEND_IMAGE__
          imagePullPolicy: IfNotPresent
          command: ["/bin/sh", "-ec"]
          args:
            - exec celery -A app.bootstrap.worker:celery_app worker --loglevel=INFO --concurrency="${CELERY_WORKER_CONCURRENCY}" --hostname="celery@${POD_NAME}"
          envFrom:
            - configMapRef:
                name: __APP__-backend-config
          env:
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: WORKER_DATABASE_URL
            - name: CELERY_BROKER_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: WORKER_CELERY_BROKER_URL
            - name: CELERY_RESULT_BACKEND
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: WORKER_CELERY_RESULT_BACKEND
                  optional: true
            - name: DOWNSTREAM_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: WORKER_DOWNSTREAM_CLIENT_SECRET
                  optional: true
          readinessProbe:
            exec:
              command:
                - /bin/sh
                - -ec
                - celery -A app.bootstrap.worker:celery_app inspect ping --destination="celery@${POD_NAME}" --timeout=3 | grep -q pong
            initialDelaySeconds: 5
            periodSeconds: 15
            timeoutSeconds: 8
            failureThreshold: 4
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-ec", "sleep 10"]
          resources:
            requests:
              cpu: 100m
              memory: 192Mi
            limits:
              cpu: "1"
              memory: 768Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 256Mi
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: __APP__-backend-worker
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-worker
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: __APP__-backend-worker
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: __APP__-backend-worker
  minReplicas: __WORKER_REPLICAS__
  maxReplicas: 8
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
    scaleUp:
      stabilizationWindowSeconds: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 75
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __APP__-backend-scheduler
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-backend
    app.kubernetes.io/component: backend-scheduler
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  replicas: 1
  revisionHistoryLimit: 3
  strategy:
    type: Recreate
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: backend-scheduler
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-backend
        app.kubernetes.io/component: backend-scheduler
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: app-platform-v2
      annotations:
        sunmoonai.com/release-id: __RELEASE_ID__
    spec:
      serviceAccountName: __APP__-backend-scheduler
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 45
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: scheduler
          image: __BACKEND_IMAGE__
          imagePullPolicy: IfNotPresent
          command: ["celery"]
          args: ["-A", "app.bootstrap.scheduler:celery_app", "beat", "--loglevel=INFO", "--schedule=/tmp/celerybeat-schedule"]
          envFrom:
            - configMapRef:
                name: __APP__-backend-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: SCHEDULER_DATABASE_URL
            - name: CELERY_BROKER_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: SCHEDULER_CELERY_BROKER_URL
          resources:
            requests:
              cpu: 25m
              memory: 96Mi
            limits:
              cpu: 250m
              memory: 256Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 64Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __APP__-admin-frontend
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-admin-frontend
    app.kubernetes.io/component: admin-frontend
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  replicas: __ADMIN_REPLICAS__
  revisionHistoryLimit: 3
  minReadySeconds: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: admin-frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-admin-frontend
        app.kubernetes.io/component: admin-frontend
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: app-platform-v2
      annotations:
        sunmoonai.com/release-id: __RELEASE_ID__
    spec:
      serviceAccountName: __APP__-admin-frontend
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              sunmoonai.com/app: __APP__
              app.kubernetes.io/component: admin-frontend
      containers:
        - name: admin
          image: __ADMIN_IMAGE__
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 3000
          envFrom:
            - configMapRef:
                name: __APP__-admin-frontend-config
          startupProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 2
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 5
            timeoutSeconds: 3
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 10
            timeoutSeconds: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-ec", "sleep 5"]
          resources:
            requests:
              cpu: 75m
              memory: 160Mi
            limits:
              cpu: 750m
              memory: 512Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: next-cache
              mountPath: /app/.next/cache
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 64Mi
        - name: next-cache
          emptyDir:
            sizeLimit: 256Mi
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: __APP__-admin-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: admin-frontend
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: __APP__-admin-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: __APP__-admin-frontend
  minReplicas: __ADMIN_REPLICAS__
  maxReplicas: 6
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __APP__-web-frontend
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-web-frontend
    app.kubernetes.io/component: web-frontend
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  replicas: __WEB_REPLICAS__
  revisionHistoryLimit: 3
  minReadySeconds: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: web-frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-web-frontend
        app.kubernetes.io/component: web-frontend
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: app-platform-v2
      annotations:
        sunmoonai.com/release-id: __RELEASE_ID__
    spec:
      serviceAccountName: __APP__-web-frontend
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              sunmoonai.com/app: __APP__
              app.kubernetes.io/component: web-frontend
      containers:
        - name: web
          image: __WEB_IMAGE__
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 3000
          envFrom:
            - configMapRef:
                name: __APP__-web-frontend-config
          startupProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 2
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 5
            timeoutSeconds: 3
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 10
            timeoutSeconds: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-ec", "sleep 5"]
          resources:
            requests:
              cpu: 75m
              memory: 160Mi
            limits:
              cpu: 750m
              memory: 512Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: next-cache
              mountPath: /app/.next/cache
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 64Mi
        - name: next-cache
          emptyDir:
            sizeLimit: 256Mi
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: __APP__-web-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      sunmoonai.com/app: __APP__
      app.kubernetes.io/component: web-frontend
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: __APP__-web-frontend
  namespace: __NAMESPACE__
  labels:
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: app-platform-v2
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: __APP__-web-frontend
  minReplicas: __WEB_REPLICAS__
  maxReplicas: 6
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
